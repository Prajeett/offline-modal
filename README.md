# Offline Gemma4 FastAPI Backend

FastAPI service for local Gemma 4 (4B) inference with:

- SSE token streaming (`/v1/chat/stream` and `/api/chat`)
- shared bearer auth
- CORS allowlist for `localhost` + `sydaux.com`
- per-IP rate limiting (`20/minute`, burst `5`)
- optional web search augmentation with toggle
- SQLite chat event persistence

## 1) Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Update `.env` with a strong `AUTH_SHARED_BEARER_TOKEN`.

## 2) Run dependencies

Run Ollama locally:

```bash
ollama run gemma4:4b
```

In another terminal, run API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 3) Test stream endpoint

```bash
curl -N -X POST "http://127.0.0.1:8000/v1/chat/stream" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role":"user","content":"Tell me a short joke"}],
    "use_search":"off"
  }'
```

## 4) Config notes

- `APP_RUNTIME_ENV=mac_test|dell_prod`
- `SEARCH_SCOPE_MODE=open|restricted`
- `CORS_ALLOWED_ORIGINS` includes localhost for testing
- TODO after testing: remove localhost origin from CORS
- edit `app/system_prompts.py` to add or update backend system prompts

