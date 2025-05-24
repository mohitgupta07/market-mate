from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.users import fastapi_users
from src.auth.database import SessionLocal
from src.auth.models import User, Conversation, Message, RoleEnum
from .lang_graph import graph
import uuid
from typing import Dict

router = APIRouter()
langgraph_memory: Dict[uuid.UUID, dict] = {}

async def get_db():
    async with SessionLocal() as session:
        yield session

@router.post("/start_session")
async def start_session(
    user: User = Depends(fastapi_users.current_user()),
    db: AsyncSession = Depends(get_db)
):
    """Start a new chat session"""
    session = Conversation(user_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    # Initialize memory
    langgraph_memory[session.id] = {"history": []}
    
    return {"session_id": str(session.id)}

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

    # Store user message
    db.add(Message(
        conversation_id=session_id,
        role=RoleEnum.user,
        content=message
    ))
    await db.commit()    # Process with LangGraph
    memory = langgraph_memory.get(session_id, {"history": []})
    result = graph(message, memory["history"])
    langgraph_memory[session_id] = {"history": result["history"]}

    # Store assistant response
    db.add(Message(
        conversation_id=session_id,
        role=RoleEnum.ai,
        content=result["output"]
    ))
    await db.commit()

    return {"reply": result["output"]}

@router.post("/restart_session/{session_id}")
async def restart_session(
    session_id: uuid.UUID,
    user: User = Depends(fastapi_users.current_user()),
    db: AsyncSession = Depends(get_db)
):
    """Restart a chat session"""
    session = await db.get(Conversation, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Clear memory if exists
    if session_id in langgraph_memory:
        del langgraph_memory[session_id]

    # Create new session
    new_session = Conversation(user_id=user.id)
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    # Initialize new memory
    langgraph_memory[new_session.id] = {"history": []}

    return {"new_session_id": str(new_session.id)}

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

@router.post("/sessions/{session_id}/resume")
async def resume_session(
    session_id: uuid.UUID,
    user: User = Depends(fastapi_users.current_user()),
    db: AsyncSession = Depends(get_db)
):
    """Resume a chat session by loading its history into memory"""
    # Get session and verify ownership
    session = await db.get(Conversation, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get messages
    result = await db.execute(
        Message.__table__.select().where(Message.conversation_id == session_id)
    )
    messages = result.fetchall()

    # Reconstruct history
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]

    # Update memory
    langgraph_memory[session_id] = {"history": history}

    return {"message": "Session resumed successfully"}
