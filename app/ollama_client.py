import json
from collections.abc import AsyncGenerator

import httpx

from app.models import ChatMessage


async def stream_ollama_chat(
    base_url: str,
    model_name: str,
    messages: list[ChatMessage],
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> AsyncGenerator[dict, None]:
    payload = {
        "model": model_name,
        "messages": [m.model_dump() for m in messages],
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    url = f"{base_url.rstrip('/')}/api/chat"
    timeout = httpx.Timeout(timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
