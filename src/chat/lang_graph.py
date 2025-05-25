from typing import Dict, Any, List, Tuple, Annotated, Sequence, TypedDict
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, Graph
from langchain_core.runnables import RunnableConfig
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain.tools import tool
from langchain.memory.chat_message_histories import PostgresChatMessageHistory
from langchain.llms.base import LLM
from src.auth.models import Message
import random
import os
import asyncio

class AgentState(TypedDict):
    messages: List[BaseMessage]

# Mock financial API tool
def mock_financial_api(query: str) -> str:
    # Simulate a financial API response
    responses = [
        f"The current price of {query} is ${random.randint(100, 500)}.",
        f"{query} is up {random.uniform(1, 5):.2f}% today.",
        f"{query} has a market cap of ${random.randint(1, 100)}B."
    ]
    return random.choice(responses)

@tool
def financial_tool(query: str) -> str:
    """Get financial data for a given query (mocked)."""
    return mock_financial_api(query)

# LiteLLM wrapper for LangChain
class LiteLLM(LLM):
    def __init__(self, api_url: str, model: str, api_key: str = None, **kwargs):
        self.api_url = api_url
        self.model = model
        self.api_key = api_key or os.getenv("LITELLM_API_KEY")
        self.kwargs = kwargs

    @property
    def _llm_type(self) -> str:
        return "litellm"

    def _call(self, prompt: str, stop: list = None) -> str:
        import requests
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {"model": self.model, "prompt": prompt}
        payload.update(self.kwargs)
        response = requests.post(self.api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get("choices", [{}])[0].get("text", "")

# --- PG Message History for stateless memory ---
def get_pg_message_history(session_id: str) -> PostgresChatMessageHistory:
    # If you want to use SQLAlchemy db connection, refactor this to use db instead of connection_string
    from langchain.memory.chat_message_histories import PostgresChatMessageHistory
    return PostgresChatMessageHistory(
        session_id=session_id,
        connection_string=os.getenv("PG_CONN_STRING"),
        table_name="chat_message_history"
    )

# --- Store summary every k messages ---
SUMMARY_EVERY_K = 10

def store_summary_to_db(session_id: str, summary: str, db):
    # Store summary in Conversation table (add a summary column if not present)
    from src.auth.models import Conversation
    from sqlalchemy import update
    db.execute(update(Conversation).where(Conversation.id == session_id).values(summary=summary))
    db.commit()

# --- Multi-turn agentic graph with LLM selection and PG memory ---
def create_graph(selected_llm: LLM, session_id: str, db=None) -> Graph:
    workflow = Graph()

    def cot_node(state: AgentState) -> Dict:
        messages = state.get("messages", [])
        messages.append(AIMessage(content="Let's think step by step."))
        return {"messages": messages}

    def tool_node(state: AgentState) -> Dict:
        messages = state.get("messages", [])
        last_user_msg = next((msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)
        if last_user_msg:
            tool_result = financial_tool(last_user_msg.content)
            messages.append(AIMessage(content=f"[Financial Tool]: {tool_result}"))
        return {"messages": messages}

    def summarizer_node(state: AgentState) -> Dict:
        messages = state.get("messages", [])
        memory = ConversationSummaryMemory(llm=selected_llm)
        for msg in messages:
            if isinstance(msg, HumanMessage):
                memory.save_context({"input": msg.content}, {})
            elif isinstance(msg, AIMessage):
                memory.save_context({}, {"output": msg.content})
        summary = memory.buffer
        messages.append(AIMessage(content=f"Summary so far: {summary}"))
        # Store summary every k messages
        if db and len([m for m in messages if isinstance(m, HumanMessage)]) % SUMMARY_EVERY_K == 0:
            store_summary_to_db(session_id, summary, db)
        return {"messages": messages}

    def buffer_memory_node(state: AgentState) -> Dict:
        messages = state.get("messages", [])
        # Use PG message history for stateless buffer
        chat_history = get_pg_message_history(session_id)
        memory = ConversationBufferMemory(chat_memory=chat_history, k=5, return_messages=True)
        for msg in messages:
            if isinstance(msg, HumanMessage):
                memory.save_context({"input": msg.content}, {})
            elif isinstance(msg, AIMessage):
                memory.save_context({}, {"output": msg.content})
        buffer = memory.buffer
        messages.append(AIMessage(content=f"Buffer memory: {buffer}"))
        return {"messages": messages}

    def aggregator_node(state: AgentState) -> Dict:
        messages = state.get("messages", [])
        ai_responses = [msg.content for msg in messages if isinstance(msg, AIMessage)]
        final_response = "\n".join(ai_responses)
        messages.append(AIMessage(content=f"Final aggregated answer: {final_response}"))
        return {"messages": messages}

    workflow.add_node("cot", cot_node)
    workflow.add_node("tool", tool_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("buffer_memory", buffer_memory_node)
    workflow.add_node("aggregator", aggregator_node)
    workflow.add_node("end", lambda state: state)
    workflow.set_entry_point("cot")
    workflow.add_edge("cot", "tool")
    workflow.add_edge("tool", "summarizer")
    workflow.add_edge("summarizer", "buffer_memory")
    workflow.add_edge("buffer_memory", "aggregator")
    workflow.add_edge("aggregator", "end")
    return workflow.compile()

def process_message(message: str, history: List[Dict[str, str]], session_id: str, llm: LLM, db=None, summary: str = None) -> Dict[str, Any]:
    messages = []
    if summary:
        # Optionally prepend summary as a system message
        messages.append(AIMessage(content=f"Summary: {summary}"))
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=message))
    state = {"messages": messages}
    graph = create_graph(llm, session_id, db)
    result = graph.invoke(state, {"config": {}}) or {"messages": []}
    final_messages = result.get("messages", [])
    assistant_message = final_messages[-1].content if final_messages else ""
    new_history = []
    for msg in final_messages:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        new_history.append({"role": role, "content": msg.content})
    return {
        "output": assistant_message,
        "history": new_history
    }

async def run_chat_graph(session, user_message: str, db):
    """
    Orchestrate the chat graph: fetch last k messages, summary, add system prompt, run COT, tool, aggregator, summarizer, and update DB.
    """
    from .lang_graph import LiteLLM, create_graph
    k = 10
    # Fetch last k messages
    result = await db.execute(
        Message.__table__.select()
        .where(Message.conversation_id == session.id)
        .order_by(Message.timestamp.desc())
        .limit(k)
    )
    messages = list(reversed(result.fetchall()))
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]
    summary = getattr(session, "summary", None)
    selected_llm_model = getattr(session, "llm_model", "gpt-3.5-turbo")
    llm = LiteLLM(api_url=os.getenv("LITELLM_API_URL"), model=selected_llm_model)
    # Build system prompt
    system_prompt = "You are a helpful AI assistant."
    # Compose state for graph
    state = {
        "messages": [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}],
        "summary": summary,
        "session_id": str(session.id),
        "db": db,
        "session": session
    }
    # Run the graph (sync for now, can be made async if needed)
    graph = create_graph(llm, str(session.id), db)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: graph.invoke(state, {"config": {}}))
    # After graph, update DB with user/AI messages and summary if needed
    # (Assume graph nodes handle DB updates for summary/messages)
    return result

# Global instance
graph = process_message
