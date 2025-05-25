from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.users import fastapi_users
from src.auth.database import SessionLocal
from src.auth.models import User, Conversation, Message, RoleEnum
from sqlalchemy import select
import uuid
from typing import Dict
import os

router = APIRouter()

async def get_db():
    async with SessionLocal() as session:
        yield session

# Example: simple rate limiter (mock, not production)
# RATE_LIMITS = {"free": 10, "pro": 100, "enterprise": 1000}  # requests per hour
# user_request_counts = {}  # In production, use Redis or similar

@router.post("/create_session")
async def create_session(
    user: User = Depends(fastapi_users.current_user()),
    db: AsyncSession = Depends(get_db),
    llm_model: str = "gpt-3.5-turbo"  # Allow user to specify model, default to gpt-3.5-turbo
):
    """Create a new chat session"""
    session = Conversation(user_id=user.id, llm_model=llm_model)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return {"session_id": str(session.id), "llm_model": session.llm_model}

@router.post("/message/{session_id}")
async def message(
    session_id: uuid.UUID,
    message: str,
    user: User = Depends(fastapi_users.current_user()),
    db: AsyncSession = Depends(get_db)
):
    """Send a message in a chat session"""
    # Get session and verify ownership
    session = await db.get(Conversation, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Call the LangGraph runner as the only handler
    from .lang_graph import run_chat_graph, update_conversation_state
    result = await run_chat_graph(session=session, user_message=message, user= user)
    await update_conversation_state(session=session, state=result["state"], db=db)
    return {"reply": result["output"]}

@router.get("/sessions")
async def list_sessions(
    user: User = Depends(fastapi_users.current_user()),
    db: AsyncSession = Depends(get_db)
):
    """List all chat sessions for the current user"""
    # Get all sessions for user
    result = await db.execute(
        Conversation.__table__.select().where(Conversation.user_id == user.id)
    )
    sessions = result.fetchall()
    
    # Format response
    formatted_sessions = []
    for session in sessions:
        # Get messages for this session
        messages_result = await db.execute(
            Message.__table__.select().where(Message.conversation_id == session.id)
        )
        messages = messages_result.fetchall()
        
        formatted_sessions.append({
            "id": str(session.id),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp
                }
                for msg in messages
            ]
        })
    
    return formatted_sessions

@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    user: User = Depends(fastapi_users.current_user()),
    db: AsyncSession = Depends(get_db)
):
    """Get details of a specific chat session"""
    # Get session and verify ownership
    session = await db.get(Conversation, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get messages
    result = await db.execute(
        Message.__table__.select().where(Message.conversation_id == session_id)
    )
    messages = result.fetchall()

    return {
        "id": str(session.id),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in messages
        ]
    }

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(fastapi_users.current_user()),
    db: AsyncSession = Depends(get_db)
):
    """Delete a chat session and its messages"""
    session = await db.get(Conversation, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"message": f"Session {session_id} deleted successfully."}
