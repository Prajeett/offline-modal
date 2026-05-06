import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.auth import validate_bearer_token
from app.config import Settings
from app.db import ChatRepository
from app.models import ChatMessage, ChatRequest
from app.ollama_client import stream_ollama_chat
from app.rate_limit import SlidingWindowRateLimiter
from app.search import should_search, simple_web_search
from app.system_prompts import build_system_prompts

settings = Settings()
repository = ChatRepository(settings.sqlite_db_path)
rate_limiter = SlidingWindowRateLimiter(
    requests_per_minute=settings.rate_limit_per_minute,
    burst=settings.rate_limit_burst,
)

active_stream_semaphore = asyncio.Semaphore(settings.max_concurrent_streams)
wait_queue = asyncio.Queue(maxsize=settings.queue_size)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="Offline Gemma4 FastAPI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_settings() -> Settings:
    return settings


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def clamp_max_tokens(request_max_tokens: int | None, conf: Settings) -> int:
    if request_max_tokens is None:
        return conf.max_tokens_default
    if request_max_tokens < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="max_tokens must be >= 1")
    return min(request_max_tokens, conf.max_tokens_hard_cap)


def sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


@app.get("/v1/health")
async def health() -> dict:
    return {"ok": True}


@app.get("/v1/ready")
async def ready() -> dict:
    return {"ok": True, "runtime_env": settings.app_runtime_env, "model": settings.model_name}


@app.post("/v1/chat/stream")
@app.post("/api/chat")
async def chat_stream(
    request: Request,
    chat_req: ChatRequest,
    authorization: str | None = Header(default=None),
    _: Settings = Depends(get_settings),
) -> StreamingResponse:
    validate_bearer_token(settings=settings, authorization=authorization)
    client_ip = get_client_ip(request)
    rate_limiter.check(client_ip)

    if wait_queue.full():
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Queue full, retry later")

    await wait_queue.put(client_ip)

    max_tokens = clamp_max_tokens(chat_req.max_tokens, settings)
    prompt_text = "\n".join(msg.content for msg in chat_req.messages)
    use_search = should_search(chat_req.use_search, prompt_text)
    system_prompts = build_system_prompts()

    async def generator() -> AsyncGenerator[str, None]:
        aggregated_response = ""
        sources_payload: list[dict] = []
        try:
            yield sse_event("meta", {"model": settings.model_name, "runtime_env": settings.app_runtime_env})

            if use_search:
                search_results = await simple_web_search(
                    query=chat_req.messages[-1].content,
                    mode=settings.search_scope_mode,
                    allowed_domains=settings.allowed_domains,
                    limit=5,
                )
                if search_results:
                    sources_payload = [r.model_dump() for r in search_results]
                    yield sse_event("source", {"results": sources_payload})
                    sources_text = "\n".join([f"- {r.title}: {r.url}\n  {r.snippet}" for r in search_results])
                    tool_context = ChatMessage(
                        role="system",
                        content=(
                            "You have fresh web snippets. Use them when relevant and cite URLs.\n"
                            f"{sources_text}"
                        ),
                    )
                    model_messages = [*system_prompts, *chat_req.messages, tool_context]
                else:
                    model_messages = [*system_prompts, *chat_req.messages]
            else:
                model_messages = [*system_prompts, *chat_req.messages]

            async with active_stream_semaphore:
                async for chunk in stream_ollama_chat(
                    base_url=settings.ollama_base_url,
                    model_name=settings.model_name,
                    messages=model_messages,
                    temperature=chat_req.temperature,
                    max_tokens=max_tokens,
                    timeout_seconds=settings.request_timeout_seconds,
                ):
                    message = chunk.get("message", {})
                    delta = message.get("content", "")
                    if delta:
                        aggregated_response += delta
                        yield sse_event("delta", {"content": delta})
                    if chunk.get("done"):
                        break

            repository.save_chat_event(
                request=chat_req,
                client_ip=client_ip,
                model_name=settings.model_name,
                response_text=aggregated_response,
                resolved_max_tokens=max_tokens,
            )
            yield sse_event(
                "done",
                {
                    "response_chars": len(aggregated_response),
                    "max_tokens": max_tokens,
                    "search_used": use_search,
                    "sources_count": len(sources_payload),
                },
            )
        except Exception as exc:  # noqa: BLE001
            yield sse_event("error", {"message": str(exc)})
        finally:
            try:
                wait_queue.get_nowait()
                wait_queue.task_done()
            except Exception:
                pass

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
