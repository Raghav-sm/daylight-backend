import os
from importlib.util import find_spec

from app.schemas.assistant import AssistantModelCatalog, AssistantModelOption

GROQ_MODEL_ID = "openai/gpt-oss-20b"
GEMINI_MODEL_ID = "gemini-3.5-flash-lite"
EFFORTS = ["low", "medium", "high"]


def _configured_secret(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def get_model_catalog() -> AssistantModelCatalog:
    groq_configured = _configured_secret("GROQ_API_KEY") is not None
    gemini_key_configured = _configured_secret("GEMINI_API_KEY", "GOOGLE_API_KEY") is not None
    gemini_adapter_installed = find_spec("langchain_google_genai") is not None
    gemini_configured = gemini_key_configured and gemini_adapter_installed

    models = [
        AssistantModelOption(
            id=GROQ_MODEL_ID,
            label="GPT OSS 20B",
            provider="Groq",
            available=groq_configured,
            supported_efforts=EFFORTS,
            unavailable_reason=None,
        ),
        AssistantModelOption(
            id=GEMINI_MODEL_ID,
            label="Gemini 3.5 Flash-Lite",
            provider="Google Gemini",
            available=gemini_configured,
            supported_efforts=EFFORTS,
            unavailable_reason=None,
        ),
    ]
    available_ids = {model.id for model in models if model.available}
    default_model_id = (
        GROQ_MODEL_ID if GROQ_MODEL_ID in available_ids
        else GEMINI_MODEL_ID if GEMINI_MODEL_ID in available_ids
        else GROQ_MODEL_ID
    )

    return AssistantModelCatalog(
        models=models,
        default_model_id=default_model_id,
        chat_enabled=bool(available_ids),
        status_message=None,
    )
