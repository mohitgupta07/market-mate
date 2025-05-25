import asyncio
import os
from typing import Dict, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
import litellm
from sqlalchemy.ext.asyncio import AsyncSession
import json
from datetime import datetime
from .models import Message, RoleEnum, Conversation, User
import uuid

# System prompt for financial data restriction and ReAct reasoning
SYSTEM_PROMPT = """
You are MarketMate, a financial market data expert. Your role is to answer queries exclusively related to financial market data, such as stock prices, company earnings, financial news, or quarterly results. Follow these guidelines:
1. Use ReAct (Reasoning + Acting) to process queries:
   - Reason: Analyze the query to determine if it pertains to financial market data (e.g., stocks, earnings, company financials). If the query is unrelated (e.g., weather, general knowledge, personal advice), conclude it’s invalid.
   - Act: For valid financial queries, determine if data retrieval is needed via function calls (Financial News API or Quarterly Financial Results API). If so, state: "I will call the [API name] to fetch the required data."
   - Evaluate: Assess the results and determine if further reasoning or actions are needed.
2. If the query is not financial-related, respond with: "Sorry, I can only assist with financial market questions. Please ask about stocks, earnings, or financial news."
3. Only call functions named 'get_financial_news' or 'get_quarterly_results'. Do not call other functions.
4. Provide clear, concise, and accurate answers based on retrieved data or reasoning.
5. If unsure, iterate up to 3 times to refine the reasoning or fetch additional data.
"""

# Mock Financial APIs
async def get_financial_news(company_name: str) -> Dict:
    return {
        "company_name": company_name,
        "news": [{"headline": f"Mock news for {company_name}", "description": "Sample news", "date": "2025-05-25", "source": "Mock"}]
    }

async def get_quarterly_results(company_name: str, quarter: str) -> Dict:
    return {
        "company_name": company_name,
        "quarter": quarter,
        "valuation_ratios": {"pe_ratio": 15.5, "pb_ratio": 2.3},
        "files": {"balance_sheet": "https://dummyfinancialapi.com/files/balance_sheet.xlsx"}
    }

# Function definitions for LLM
FUNCTIONS = [
    {
        "name": "get_financial_news",
        "description": "Fetch financial news for a company",
        "parameters": {
            "type": "object",
            "properties": {"company_name": {"type": "string"}},
            "required": ["company_name"]
        }
    },
    {
        "name": "get_quarterly_results",
        "description": "Fetch quarterly financial results for a company",
        "parameters": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string"},
                "quarter": {"type": "string"}
            },
            "required": ["company_name", "quarter"]
        }
    }
]

# Function map for tool calls
FUNCTION_MAP = {
    "get_financial_news": get_financial_news,
    "get_quarterly_results": get_quarterly_results
}

# LangGraph State
class ChatState(BaseModel):
    session_id: str
    user_id: str
    tier: str
    user_query: str
    messages: List[Dict[str, str]] = []
    summary: Optional[str] = None
    response: Optional[str] = None
    is_financial: Optional[bool] = None
    llm_client: Optional[Dict] = None
    iteration: int = 0
    max_iterations: int = 3
    user_message_count: int = 0  # Track user messages for summary updates

# Input Node: Load messages and prepare state
async def input_node(state: ChatState) -> ChatState:
    # Messages already provided by caller (last K user/AI messages)
    state.messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    
    # Count user messages for summary update condition
    state.user_message_count = sum(1 for msg in state.messages if msg["role"] == "human")
    return state

# CoT Node: ReAct-based reasoning and action
async def cot_node(state: ChatState) -> ChatState:
    if state.iteration >= state.max_iterations:
        state.response = "Unable to process query after maximum reasoning attempts."
        return state
    
    # Prepare messages for LLM
    messages = state.messages + [{"role": "user", "content": state.user_query}]
    if state.summary:
        messages.insert(1, {"role": "system", "content": f"Conversation summary: {state.summary}"})
    
    # Call LLM to reason about query domain and actions
    reasoning_prompt = f"""
    Analyze the following query: "{state.user_query}"
    Step 1: Reason about whether the query pertains to financial market data (e.g., stocks, earnings, company financials).
    Step 2: If non-financial, conclude the query is invalid and respond with the rejection message.
    Step 3: If financial, determine if a function call is needed to fetch data (e.g., Financial News API or Quarterly Financial Results API).
    Step 4: If a function call is needed, specify which function and arguments.
    Provide your reasoning and conclusion in a structured JSON format:
    ```json
    {
        "reasoning": ["step 1", "step 2", ...],
        "is_financial": true/false,
        "function_call": {"name": "function_name", "arguments": {...}} or null,
        "response": "text response if no function call or invalid query"
    }
    ```
    """
    messages.append({"role": "system", "content": reasoning_prompt})
    
    try:
        response = await litellm.acompletion(
            model=state.llm_client["model"],
            provider=state.llm_client["provider"],
            api_key=state.llm_client["api_key"],
            messages=messages,
            functions=FUNCTIONS,  # Pass available functions
            function_call="auto",
            temperature=0.7,
            metadata=state.llm_client["metadata"]
        )
        
        llm_message = response.choices[0].message
        try:
            reasoning_result = json.loads(llm_message.content) if llm_message.content else {}
        except json.JSONDecodeError:
            reasoning_result = {
                "reasoning": ["Failed to parse LLM output as JSON"],
                "is_financial": False,
                "function_call": None,
                "response": "Sorry, I encountered an error processing your query."
            }
        
        state.is_financial = reasoning_result.get("is_financial", False)
        state.messages.append({"role": "assistant", "content": llm_message.content or json.dumps(reasoning_result)})
        
        if not state.is_financial:
            state.response = reasoning_result.get("response", "Sorry, I can only assist with financial market questions. Please ask about stocks, earnings, or financial news.")
            return state
        
        if reasoning_result.get("function_call"):
            state.messages.append({"role": "assistant", "content": json.dumps(reasoning_result)})
            return state
        
        if reasoning_result.get("response"):
            state.response = reasoning_result["response"]
            return state
        
        # Loop back to CoT if response is incomplete
        state.iteration += 1
        return state
    
    except Exception as e:
        state.response = f"Error processing query: {str(e)}"
        state.is_financial = False
        return state

# Tool Call Node: Execute function calls
async def tool_call_node(state: ChatState) -> ChatState:
    if state.iteration >= state.max_iterations:
        state.response = "Unable to process query after maximum function calls."
        return state
    
    last_message = state.messages[-1]
    try:
        reasoning_result = json.loads(last_message["content"]) if last_message["content"] else {}
    except json.JSONDecodeError:
        state.response = "Invalid reasoning output from previous step."
        return state
    
    function_call = reasoning_result.get("function_call")
    
    if not function_call:
        state.response = "No function call specified."
        return state
    
    function_name = function_call.get("name")
    args = function_call.get("arguments", {})
    
    if function_name not in FUNCTION_MAP:
        state.response = "Invalid function call detected."
        return state
    
    try:
        result = await FUNCTION_MAP[function_name](**args)
        state.messages.append({"role": "function", "content": json.dumps(result)})
    except Exception as e:
        state.response = f"Error executing function {function_name}: {str(e)}"
        return state
    
    state.iteration += 1
    return state

# Invalid Query Node: Handle non-financial queries
async def invalid_query_node(state: ChatState) -> ChatState:
    state.response = state.response or "Sorry, I can only assist with financial market questions. Please ask about stocks, earnings, or financial news."
    state.messages.append({"role": "assistant", "content": state.response})
    return state

# Summarizer Node: Update summary for every Kth user message
async def summarizer_node(state: ChatState) -> ChatState:
    K = 10
    if state.user_message_count % K == 0 and state.user_message_count > 0:
        try:
            summary_response = await litellm.acompletion(
                model=state.llm_client["model"],
                provider=state.llm_client["provider"],
                api_key=state.llm_client["api_key"],
                messages=[{"role": "system", "content": "Summarize the conversation concisely, focusing on financial topics."}] + state.messages,
                temperature=0.5,
                metadata=state.llm_client["metadata"]
            )
            state.summary = summary_response.choices[0].message.content
        except Exception as e:
            state.summary = state.summary or ""  # Retain existing summary on error
    return state

# Output Node: Prepare state for external DB update
async def output_node(state: ChatState) -> ChatState:
    return state

# Build Workflow
def build_workflow() -> CompiledStateGraph:
    workflow = StateGraph(ChatState)
    
    workflow.add_node("input", input_node)
    workflow.add_node("cot", cot_node)
    workflow.add_node("tool_call", tool_call_node)
    workflow.add_node("invalid_query", invalid_query_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("output", output_node)
    
    workflow.set_entry_point("input")
    workflow.add_edge("input", "cot")
    workflow.add_conditional_edges(
        "cot",
        lambda state: (
            "invalid_query" if not state.is_financial else
            "tool_call" if json.loads(state.messages[-1]["content"]).get("function_call") else
            "cot" if not state.response and state.iteration < state.max_iterations else
            "summarizer"
        )
    )
    workflow.add_edge("tool_call", "cot")  # Loop back to CoT for ReAct iteration
    workflow.add_edge("invalid_query", "output")
    workflow.add_edge("summarizer", "output")
    workflow.add_edge("output", END)
    
    return workflow.compile()

# Database Update Function
async def update_conversation_state(session: Conversation, state: ChatState, db: AsyncSession) -> None:
    """
    Update the conversation state in the database.
    
    Args:
        session: Conversation object from DB
        state: ChatState object from LangGraph
        db: Async SQLAlchemy session
    """
    # Add user message
    user_message = Message(
        conversation_id=session.id,
        role=RoleEnum.human,
        content=state.user_query,
        timestamp=datetime.utcnow()
    )
    db.add(user_message)
    
    # Add AI response (if any)
    if state.response:
        ai_message = Message(
            conversation_id=session.id,
            role=RoleEnum.ai,
            content=state.response,
            timestamp=datetime.utcnow()
        )
        db.add(ai_message)
    
    # Update summary
    session.summary = state.summary or session.summary
    session.updated_at = datetime.utcnow()
    
    await db.commit()

# Exposed Function for FastAPI
async def run_chat_graph(session: Conversation, user_message: str, user: User) -> Dict:
    """
    Run the LangGraph workflow for a chat session.
    
    Args:
        session: Conversation object from DB with session_id, user_id, messages, summary
        user_message: User input message
        user: FastAPI-Users user object with id and tier
    
    Returns:
        Dict with 'output' key containing the LLM response and 'state' for DB updates
    """
    # Fetch last K=10 user/AI messages
    K = 10
    messages = [
        {"role": msg.role.value, "content": msg.content}
        for msg in session.messages
        if msg.role in [RoleEnum.human, RoleEnum.ai]
    ][-K:]
    
    workflow = build_workflow()
    state = ChatState(
        session_id=str(session.id),
        user_id=str(user.id),
        tier=user.tier,
        user_query=user_message,
        messages=messages,
        summary=session.summary or "",
        user_message_count=len([msg for msg in session.messages if msg.role == RoleEnum.human]) + 1,
        llm_client={
            "model": session.llm_model,
            "provider": "openai",
            "api_key": os.getenv("LITELLM_API_KEY"),
            "metadata": {"user_id": str(user.id), "tier": user.tier}
        }
    )
    result = await workflow.ainvoke(state)
    return {"output": result.response or "No response generated.", "state": result}