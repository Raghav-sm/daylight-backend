import os

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from app.assistant.model_catalog import GEMINI_MODEL_ID, GROQ_MODEL_ID

GROQ_CHAT_URL = "https://api.groq.com/openai/v1"


def build_chat_model(model_id: str, effort: str) -> BaseChatModel:
    """Create an OpenAI-compatible provider adapter with backend-only credentials."""
    if model_id == GROQ_MODEL_ID:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured on the backend.")
        return ChatOpenAI(
            model=GROQ_MODEL_ID,
            api_key=api_key,
            base_url=GROQ_CHAT_URL,
            reasoning_effort=effort,
            # Groq GPT-OSS models use `include_reasoning` rather than `reasoning_format`.
            extra_body={"include_reasoning": False},
            timeout=45,
            max_retries=1,
        )

    if model_id == GEMINI_MODEL_ID:
        api_key = os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured on the backend.")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as error:
            raise RuntimeError("Install the optional Gemini adapter with `uv sync --extra gemini`.") from error

        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_ID,
            google_api_key=api_key,
            thinking_level=effort,
            timeout=45,
            max_retries=1,
        )

    raise ValueError("Unsupported assistant model.")
