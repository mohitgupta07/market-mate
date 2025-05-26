import pytest
from src.chat.lang_graph import run_chat_graph, update_conversation_state
from src.auth.models import User, Conversation, Message, RoleEnum
import uuid
from datetime import datetime

@pytest.mark.asyncio
async def test_financial_query_with_function_call(db, user, session):
    user.tier = "free"
    session.messages = []
    session.summary = ""
    session.llm_model = "gpt-40"
    result = await run_chat_graph(session=session, user_message="What are Apple's latest earnings?", user=user)
    assert "valuation_ratios" in result["output"]  # Mock API response
    await update_conversation_state(session=session, state=result["state"], db=db)
    assert len(session.messages) == 2  # User message + AI response
    assert session.messages[0].role == RoleEnum.human
    assert session.messages[1].role == RoleEnum.ai

@pytest.mark.asyncio
async def test_non_financial_query(db, user, session):
    user.tier = "free"
    session.messages = []
    session.summary = ""
    session.llm_model = "gpt-40"
    result = await run_chat_graph(session=session, user_message="What's the weather?", user=user)
    assert "Sorry, I can only assist with financial market questions" in result["output"]
    await update_conversation_state(session=session, state=result["state"], db=db)
    assert len(session.messages) == 2
    assert session.messages[0].role == RoleEnum.human
    assert session.messages[1].role == RoleEnum.ai

@pytest.mark.asyncio
async def test_summary_update(db, user, session):
    user.tier = "free"
    session.messages = [Message(
        conversation_id=session.id,
        role=RoleEnum.human,
        content=f"Query {i}",
        timestamp=datetime.utcnow()
    ) for i in range(9)]
    session.summary = ""
    session.llm_model = "gpt-40"
    result = await run_chat_graph(session=session, user_message="What are Apple's earnings?", user=user)
    await update_conversation_state(session=session, state=result["state"], db=db)
    assert session.summary  # Summary updated on 10th user message