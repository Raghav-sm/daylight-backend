from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import AssistantConversation, AssistantMessage
from app.schemas.assistant import AssistantConversationRead, AssistantConversationSummary


def list_conversations(db: Session, owner_id: str) -> list[AssistantConversationSummary]:
    rows = db.scalars(
        select(AssistantConversation)
        .where(AssistantConversation.owner_id == owner_id)
        .order_by(AssistantConversation.updated_at.desc())
        .limit(50)
    ).all()
    return [AssistantConversationSummary.model_validate(row) for row in rows]


def get_conversation(db: Session, conversation_id: str, owner_id: str) -> AssistantConversation:
    conversation = db.scalar(
        select(AssistantConversation)
        .options(selectinload(AssistantConversation.messages))
        .where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.owner_id == owner_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def conversation_read(conversation: AssistantConversation) -> AssistantConversationRead:
    return AssistantConversationRead(
        id=conversation.id,
        title=conversation.title,
        model_id=conversation.model_id,
        effort=conversation.effort,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=conversation.messages,
    )


def save_exchange(
    db: Session,
    *,
    owner_id: str,
    conversation: AssistantConversation | None,
    message: str,
    answer: str,
    model_id: str,
    effort: str,
    project_id: str | None,
    project_name: str | None,
    graph_state: list[dict],
) -> AssistantConversation:
    now = datetime.now(timezone.utc)
    if conversation is None:
        conversation = AssistantConversation(
            owner_id=owner_id,
            title=message.strip().replace("\n", " ")[:120] or "New conversation",
            model_id=model_id,
            effort=effort,
            graph_state=graph_state,
            graph_state_model_id=model_id,
            created_at=now,
            updated_at=now,
        )
        db.add(conversation)
        db.flush()
        current_position = 0
    else:
        current_position = max((item.position for item in conversation.messages), default=-1) + 1
        conversation.model_id = model_id
        conversation.effort = effort
        conversation.updated_at = now
        conversation.graph_state = graph_state
        conversation.graph_state_model_id = model_id

    conversation.messages.extend(
        [
            AssistantMessage(
                role="user",
                content=message,
                project_id=project_id,
                project_name=project_name,
                position=current_position,
                created_at=now,
            ),
            AssistantMessage(
                role="assistant",
                content=answer,
                model_id=model_id,
                effort=effort,
                position=current_position + 1,
                created_at=now,
            ),
        ]
    )
    db.commit()
    return get_conversation(db, conversation.id, owner_id)
