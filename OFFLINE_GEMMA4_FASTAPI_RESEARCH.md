# Offline Gemma 4 + FastAPI Streaming API (Research + Execution Brief)

## Goal

Build a local AI backend that runs on your own machine, serves streamed responses through FastAPI, supports concurrent requests with good performance, and can optionally do online search based on prompt intent.

This brief includes:
- Deep research conclusions
- Updated requirements you provided
- Recommended architecture
- Security and deployment best practices
- Open questions needed before implementation

## Updated Requirements (from user)

- Development machine: Mac M1
- Runtime/hosting machine: Dell i5 8th gen PC
- Model: Gemma 4 (4B)
- Throughput goal: concurrent requests with good performance
- Concurrency target: 5 active requests at a time
- Streaming protocol: SSE
- Online search: simple scraping approach
- Search scope mode: unrestricted web for now, configurable via variable/toggle
- Security: run on local machine, API callable globally with token auth
- CORS origins during testing: `http://localhost` and `https://www.sydaux.com` only
- Public API entrypoint target: `https://sydaux.com/api/chat`
- Local testing entrypoint: `http://localhost` (remove later)
- CORS post-testing target: `https://www.sydaux.com` only
- Token model: single shared bearer token
- Memory: SQLite (local DB)
- Deployment: simple local-machine deployment
- Cross-site usage: external sites/apps should call API using token
- Primary client mode: browser users on public `https://www.sydaux.com` should receive streamed LLM responses
- Dedicated API subdomain: not required for now

## Research Highlights

## 1) Model Runtime Choice

- `Ollama` is the fastest path for local deployment and stable model serving APIs.
- `vLLM` is generally stronger for high-concurrency throughput in GPU-heavy environments, but setup and hardware expectations are higher.
- For Dell i5 8th gen CPU-first setup, start with `Ollama` for practicality and maintainability.

## 2) Gemma 4 Licensing

- Gemma 4 licensing page points to Apache 2.0 terms.
- Action item: pin the exact model artifact/tag used in production and keep attribution/compliance notes in repo docs.

## 3) FastAPI Streaming

- Use FastAPI `StreamingResponse` with `text/event-stream` for SSE.
- Stream chunk-by-chunk from model runtime to client with cancellation-aware async generators.

## 4) CORS + Token Auth

- If browser clients need `Authorization` header, avoid wildcard CORS with credentials.
- Prefer explicit origin allowlist and bearer token validation.
- For server-to-server callers, CORS is not relevant; token auth still required.

## 5) Search Tooling

- Implement conditional search routing (do not scrape for every prompt).
- Trigger search for "latest/current/news/recent/live" or when model/tool policy asks for external info.
- Return provenance in answer (URLs used).

## 6) Exposing Home-Hosted API (2026 Recommendation)

- Recommended: **Cloudflare Tunnel** as the default way to expose your home-hosted API.
- Why this is preferred over direct port-forwarding:
  - no inbound router port opening required
  - stable HTTPS endpoint with your own domain
  - better security posture with edge protection controls
- Backup option: Tailscale Funnel for quick sharing/testing, but Cloudflare Tunnel is better for public website integration.

## Practical Performance Note for Dell i5 8th Gen

Gemma 4 4B on older CPU hardware can be usable but may not be fast under concurrency without tuning. To maintain "good performance", use:

- Request queue + worker limits
- Max token caps
- Timeout budgets
- Response caching for repeated prompts
- Potential fallback model for heavy load (optional)

If 4B throughput is too low in real tests, keep Gemma 4 4B as primary but allow degradation mode (shorter max tokens or reduced concurrent workers).

### Token Budget for 5-minute Responses

- Fast hosted GPUs can generate far more than this, but your Dell i5 8th gen CPU is expected to be significantly slower for Gemma 4 4B.
- Practical planning assumption for CPU-only local serving: around `1-3 tokens/sec`.
- In 5 minutes (`300s`), practical output range is roughly `300-900 tokens`.
- Recommended limits:
  - `max_tokens_default = 700`
  - `max_tokens_hard_cap = 900`
  - `request_timeout_seconds = 300` (5 minutes hard cap)

## Proposed System Architecture

## Components

1. **API Gateway Layer (FastAPI)**
   - `/v1/chat/stream` (SSE)
   - `/v1/health` and `/v1/ready`
   - Auth middleware/dependency for bearer token
   - Request validation + rate limit

2. **Inference Adapter**
   - Wrapper for Ollama `/api/chat` streaming
   - Converts Ollama stream chunks into SSE events
   - Handles cancellation and cleanup

3. **Search Adapter (Simple Scraping)**
   - Lightweight fetch/scrape function
   - Domain allowlist + timeout + retries
   - Returns compact snippets and URLs only

4. **Policy Router**
   - Decides: direct answer vs search-augmented answer
   - Prompt-intent classifier rules (deterministic first version)

5. **Memory Store**
   - Option A: SQLite (fastest to start locally)
   - Option B: Postgres (better for scale/remote durability)
   - Store conversations by `session_id` + token usage + metadata

6. **Ops/Safety**
   - Structured logs + request IDs
   - Global timeout and per-stage timeout
   - Secrets in environment variables

## API Contract (Recommended)

Endpoint: `POST /v1/chat/stream`

Request body:
- `session_id` (optional)
- `messages` (chat history)
- `use_search` (optional override: auto/on/off)
- generation params (`temperature`, `max_tokens`, etc.)

SSE event types:
- `meta`: request accepted, model info
- `delta`: token chunks
- `source`: emitted when web sources are used
- `done`: completion payload with usage stats
- `error`: typed error event

## Concurrency Strategy (CPU-First)

- Use one model service process and a bounded async queue.
- Limit active generations to `N=5` to avoid CPU thrashing.
- Backpressure behavior:
  - queue if under threshold
  - reject with 429 when queue full
- Add per-request token cap and max duration.

## Security Design

- Bearer token auth required on all non-health endpoints.
- Optional token rotation support.
- Restrict admin endpoints by separate token/scope.
- CORS:
  - Allow origins explicitly: `http://localhost` (testing) and `https://www.sydaux.com`.
  - Add TODO comment in config to remove localhost after testing.
  - Final production target: `https://www.sydaux.com` only.
  - Do not use wildcard origins.
  - Keep `Authorization` header allowed for bearer token usage from browser clients.
- Browser security note:
  - A shared bearer token in frontend code can be exposed to users.
  - Preferred production pattern is to proxy LLM calls through your website backend so the token stays server-side.
  - Decision: use a safer backend proxy flow with your Next.js app.
- Expose publicly via router + firewall + reverse proxy (optional), but keep rate limiting and auth enforced.

### Next.js Safer Proxy Pattern (Chosen)

- Browser calls your Next.js API route (same origin as `https://www.sydaux.com`).
- Public route target: `https://sydaux.com/api/chat`.
- Next.js server route forwards the request to FastAPI with the shared bearer token in server-side env vars.
- SSE stream is relayed from FastAPI back to the browser.
- Benefit: token is never exposed to end users in client-side code.

## Deployment on Local Machine (Simple)

Baseline:
- Python venv + FastAPI app (`uvicorn`)
- Ollama running as local service
- `.env` for tokens and config
- Cloudflare Tunnel agent (`cloudflared`) for secure public ingress from home network
- Optional system service:
  - Linux (Dell): `systemd` unit for auto-restart on boot

## Runtime and Feature Variables (Config-First)

Use environment variables so you can test on Mac first and then move to Dell without code changes.

- `APP_RUNTIME_ENV`: `mac_test` | `dell_prod`
- `MODEL_RUNTIME`: `ollama` (default)
- `MODEL_NAME`: `gemma4:4b`
- `MAX_CONCURRENT_STREAMS`: `5`
- `QUEUE_SIZE`: `20`
- `MAX_TOKENS_DEFAULT`: `700`
- `MAX_TOKENS_HARD_CAP`: `900`
- `REQUEST_TIMEOUT_SECONDS`: `300`
- `AUTH_SHARED_BEARER_TOKEN`: `<your_token>`
- `CORS_ALLOWED_ORIGINS`: `http://localhost,https://www.sydaux.com`
- `SEARCH_SCOPE_MODE`: `open` | `restricted`
- `SEARCH_ALLOWED_DOMAINS`: empty when `open`, comma-separated list when `restricted`
- `SQLITE_DB_PATH`: `./data/app.db`
- `TUNNEL_PROVIDER`: `cloudflare`

Recommended config comment to include in code:
- `# TODO: remove http://localhost from CORS_ALLOWED_ORIGINS after testing`

## Recommended Data Layer Choice

Start with **SQLite** for simplicity, then move to Postgres if needed.

Why:
- You requested simple local deployment.
- SQLite avoids DB service overhead.
- Easy migration path to Postgres via SQLAlchemy/Alembic later.

## Implementation Plan (Next Step)

1. Scaffold FastAPI app with config, auth, and SSE endpoint.
2. Add Ollama streaming adapter for Gemma 4 4B.
3. Add conditional web scraping tool and source citation events.
4. Add memory persistence (SQLite first, Postgres-ready models).
5. Add queue/concurrency guardrails and rate limiting.
6. Add deployment scripts and runbook for Dell machine.
7. Add load test script for concurrent requests and tuning guide.

## Remaining Questions (Need your answers)

No blocking questions remaining for implementation setup.

## Suggested Defaults If You Want Me To Proceed Immediately

- Runtime: Ollama + Gemma 4 4B
- API: FastAPI SSE endpoint
- Auth: static bearer token from `.env`
- DB: SQLite
- Concurrency: 5 active streams, queue 20
- Timeout: 300s hard request timeout
- Max tokens: 700 default, 900 hard cap
- Search: auto mode with keyword trigger + URL citations
- Search scope: unrestricted (`SEARCH_SCOPE_MODE=open`) with toggle to restricted
- CORS allowlist: `http://localhost`, `https://www.sydaux.com`
- CORS TODO: remove localhost after testing
- Ingress: Cloudflare Tunnel
- Client path: browser users on `https://www.sydaux.com`
- Subdomain: no dedicated API subdomain for now
- Public API route: `https://sydaux.com/api/chat`
- Local test route: `http://localhost/...`
- Web integration: Next.js backend proxy (token kept server-side)
- Rate limit: `20 requests/minute` per IP, burst `5`

