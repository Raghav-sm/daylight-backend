import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.assistant.conversations import (
    conversation_read,
    get_conversation,
    list_conversations,
    save_exchange,
)
from app.assistant.model_catalog import get_model_catalog
from app.database import get_db
from app.models import AuthSession, User
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantConversationRead,
    AssistantConversationSummary,
    AssistantModelCatalog,
)
from app.security.dependencies import get_current_user, require_csrf
from app.services import project_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/models", response_model=AssistantModelCatalog)
def get_models(_user: User = Depends(get_current_user)) -> AssistantModelCatalog:
    """Return configured model choices without returning provider credentials."""
    return get_model_catalog()


@router.get("/conversations", response_model=list[AssistantConversationSummary])
def get_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AssistantConversationSummary]:
    return list_conversations(db, user.id)


@router.get("/conversations/{conversation_id}", response_model=AssistantConversationRead)
def get_conversation_detail(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssistantConversationRead:
    return conversation_read(get_conversation(db, conversation_id, user.id))


@router.post("/chat", response_model=AssistantConversationRead)
def chat(
    request: AssistantChatRequest,
    user: User = Depends(get_current_user),
    _csrf: AuthSession = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> AssistantConversationRead:
    catalog = get_model_catalog()
    model = next((item for item in catalog.models if item.id == request.model_id), None)
    if model is None or not model.available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That model is not configured.")
    if request.effort not in model.supported_efforts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That reasoning effort is not supported by the selected model.",
        )

    conversation = None
    history = []
    try:
        from langchain_core.messages import AIMessage, HumanMessage, messages_from_dict

        from app.assistant.graph import run_agent
    except ImportError as error:
        logger.exception("Assistant runtime dependencies are not installed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Install the backend assistant dependencies before using chat.",
        ) from error

    if request.conversation_id:
        conversation = get_conversation(db, request.conversation_id, user.id)
        if conversation.graph_state and conversation.graph_state_model_id == request.model_id:
            history = messages_from_dict(conversation.graph_state)
        else:
            for saved in conversation.messages:
                if saved.role == "user":
                    content = saved.content
                    if saved.project_name:
                        content = f"[Selected project context: {saved.project_name}]\n{content}"
                    history.append(HumanMessage(content=content))
                elif saved.role == "assistant":
                    history.append(AIMessage(content=saved.content))

    project_name = None
    selected_project = None
    if request.project_id:
        project = project_service.get_project(db, request.project_id, user.id)
        project_name = project.name
        selected_project = f"{project.name} (project id {project.id})"

    current_message = request.message.strip()
    graph_message = current_message
    if selected_project:
        graph_message = f"[Selected project context: {selected_project}]\n{current_message}"
    history.append(HumanMessage(content=graph_message))

    try:
        answer, graph_state = run_agent(
            owner_id=user.id,
            model_id=request.model_id,
            effort=request.effort,
            messages=history,
        )
    except Exception as error:
        logger.exception("Daylight assistant turn failed for user %s", user.id)
        message = str(error)
        if "not configured" in message.lower():
            raise HTTPException(status_code=503, detail=message) from error
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The assistant could not complete this message. Your conversation was not saved.",
        ) from error

    if not answer:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The assistant returned an empty response. Your conversation was not saved.",
        )

    saved_conversation = save_exchange(
        db,
        owner_id=user.id,
        conversation=conversation,
        message=current_message,
        answer=answer,
        model_id=request.model_id,
        effort=request.effort,
        project_id=request.project_id,
        project_name=project_name,
        graph_state=graph_state,
    )
    return conversation_read(saved_conversation)
