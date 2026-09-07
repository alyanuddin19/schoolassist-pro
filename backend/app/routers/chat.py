"""AI assistant chat endpoint (dashboard controller with safe actions)."""

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import OrgContext, get_org_context
from ..models import AiChatMessage, AiChatSession
from ..schemas import ChatRequest, ChatResponse
from ..services import chat_engine

router = APIRouter(prefix="/chat", tags=["ai-chat"])


def _get_or_create_session(db, ctx: OrgContext, request: ChatRequest) -> AiChatSession:
    if request.session_id:
        session = (
            db.query(AiChatSession)
            .filter(
                AiChatSession.id == request.session_id,
                AiChatSession.organization_id == ctx.org_id,
                AiChatSession.user_id == ctx.user.id,
            )
            .first()
        )
        if session is not None:
            return session
    session = AiChatSession(
        organization_id=ctx.org_id,
        user_id=ctx.user.id,
        title=request.message[:120],
        language=request.language,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, ctx: OrgContext = Depends(get_org_context)):
    """Send a message to the Qwen-powered assistant.

    The reply is either a normal answer or a structured action that the
    backend executes safely (permission-checked, org-scoped) and returns
    together with a display payload for the frontend.
    """
    session = _get_or_create_session(ctx.db, ctx, request)
    chat_engine.persist_turn(ctx.db, session, "user", request.message, None)

    reply, action, action_result, action_status = chat_engine.run_chat_turn(
        ctx.db, ctx, request, session
    )
    chat_engine.persist_turn(
        ctx.db, session, "assistant", reply, action if action else None
    )

    return ChatResponse(
        session_id=session.id,
        reply=reply,
        action=action,
        action_status=action_status,
        action_result=action_result,
    )


@router.get("/sessions")
def list_sessions(ctx: OrgContext = Depends(get_org_context)):
    sessions = (
        ctx.db.query(AiChatSession)
        .filter(
            AiChatSession.organization_id == ctx.org_id,
            AiChatSession.user_id == ctx.user.id,
        )
        .order_by(AiChatSession.created_at.desc())
        .limit(30)
        .all()
    )
    return [
        {"id": s.id, "title": s.title, "language": s.language, "created_at": s.created_at.isoformat() if s.created_at else None}
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: int, ctx: OrgContext = Depends(get_org_context)):
    session = (
        ctx.db.query(AiChatSession)
        .filter(
            AiChatSession.id == session_id,
            AiChatSession.organization_id == ctx.org_id,
            AiChatSession.user_id == ctx.user.id,
        )
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    messages = (
        ctx.db.query(AiChatMessage)
        .filter(AiChatMessage.session_id == session.id)
        .order_by(AiChatMessage.id.asc())
        .all()
    )
    return [
        {
            "role": m.role,
            "content": m.content,
            "action": m.action,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
