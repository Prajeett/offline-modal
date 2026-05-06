from app.models import ChatMessage

# Edit this list to customize backend system prompts.
# Prompts are applied in order before user messages.
SYSTEM_PROMPT_TEXTS: list[str] = [
    (
        "Respond in plain text only. Preserve line breaks when useful. "
        "Do not use markdown formatting symbols such as *, **, #, or backticks."
    ),
]


def build_system_prompts() -> list[ChatMessage]:
    prompts: list[ChatMessage] = []
    for text in SYSTEM_PROMPT_TEXTS:
        cleaned = text.strip()
        if cleaned:
            prompts.append(ChatMessage(role="system", content=cleaned))
    return prompts
