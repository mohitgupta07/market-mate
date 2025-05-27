import asyncio
import os
from typing import Dict, List, Optional

import pytest_asyncio
from langchain.chains.question_answering.map_reduce_prompt import messages
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel
import litellm
from sqlalchemy.ext.asyncio import AsyncSession
import json
from datetime import datetime
from src.auth.models import Message, RoleEnum, Conversation, User
import structlog
from prometheus_client import Counter
from tenacity import retry, stop_after_attempt, wait_fixed
from src.chat.prompt import SYSTEM_PROMPT, REASONING_PROMPT_TEMPLATE
from src.chat.functions_list import FUNCTIONS, FUNCTION_MAP


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
    max_iterations: int = 7
    user_message_count: int = 0
    finish_reason: Optional[str] = None

# Structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# Metrics
cot_iterations = Counter("cot_node_iterations", "Number of CoT node iterations")
function_calls = Counter("function_calls", "Number of function calls", ["function_name"])
errors = Counter("workflow_errors", "Number of errors in workflow", ["node"])

# LLM Wrapper
async def call_llm(state: ChatState, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict:
    logger.info(
        "Calling LLM",
        session_id=state.session_id,
        model=state.llm_client["model"],
        api_base=state.llm_client["api_base"]
    )
    try:
        response = await litellm.acompletion(
            model=state.llm_client["model"],
            api_key=state.llm_client["api_key"],
            messages=messages,
            temperature=temperature,
            metadata=state.llm_client["metadata"],
            tools=FUNCTIONS,
            tool_choice="auto"
        )
        logger.info("LLM response received", model=state.llm_client["model"],
                    response_metadata=response.get("metadata", {}))
        return response
    except Exception as e:
        logger.error("Error in LLM call", session_id=state.session_id, error=str(e))
        errors.labels(node="llm_call").inc()
        raise

# Input Node
async def input_node(state: ChatState) -> ChatState:
    logger.info("Entering input node", session_id=state.session_id, user_query=state.user_query)
    state.messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    state.user_message_count = sum(1 for msg in state.messages if msg["role"] == "human")
    return state

# CoT Node
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
async def cot_node(state: ChatState) -> ChatState:
    logger.info(
        "Entering CoT node",
        session_id=state.session_id,
        iteration=state.iteration,
        model=state.llm_client["model"],
        api_base=state.llm_client["api_base"]
    )
    cot_iterations.inc()

    if state.iteration >= state.max_iterations:
        state.response = "Unable to process query after maximum reasoning attempts."
        logger.warning("Max iterations reached", session_id=state.session_id)
        return state
    messages = state.messages
    if state.iteration == 0:
        messages = messages + [{"role": "user", "content": state.user_query}]
    if state.summary:
        messages.insert(1, {"role": "system", "content": f"Conversation summary: {state.summary}"})

    try:
        response = await call_llm(state, messages, temperature=0.7)
        llm_message = response.choices[0].message
        state.finish_reason = response.choices[0].finish_reason
        content = llm_message.content or ""

        # Handle tool calls if present
        if llm_message.tool_calls:
            state.messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    } for tool_call in llm_message.tool_calls
                ]
            })
            # Set is_financial based on whether the tool call is 'invalid'
            if state.iteration == 0:
                state.is_financial = not any(tc.function.name == "invalid" for tc in llm_message.tool_calls)
                logger.info("Financial status determined", session_id=state.session_id, is_financial=state.is_financial)
            logger.info("Tool call detected", session_id=state.session_id,
                        tool_calls=[tc.function.name for tc in llm_message.tool_calls])
            return state

        # Handle non-tool-call responses
        state.messages.append({"role": "assistant", "content": content})

        # For non-tool-call responses, assume financial in first iteration unless clarified by prompt
        if state.iteration == 0:
            state.is_financial = True  # Default to True; prompt should call invalid() for non-financial
            logger.info("Financial status determined (default)", session_id=state.session_id, is_financial=state.is_financial)

        if state.finish_reason == "stop" and not llm_message.tool_calls:
            state.response = content or "Please provide more details to proceed with your query."
            logger.info("Clarification request detected", session_id=state.session_id, response=state.response)
            return state

        if content:
            state.response = content
            logger.info("Final response generated", session_id=state.session_id)
            return state

        state.iteration += 1
        logger.info("Incomplete response, looping back", session_id=state.session_id, iteration=state.iteration)
        return state

    except Exception as e:
        logger.error("Error in CoT node", session_id=state.session_id, error=str(e))
        errors.labels(node="cot").inc()
        state.response = f"Error processing query: {str(e)}"
        state.is_financial = False
        return state

# Tool Call Node
async def tool_call_node(state: ChatState) -> ChatState:
    logger.info("Entering tool call node", session_id=state.session_id, iteration=state.iteration)

    if state.iteration >= state.max_iterations:
        state.response = "Unable to process query after maximum function calls."
        logger.warning("Max iterations reached in tool call", session_id=state.session_id)
        return state

    last_message = state.messages[-1]
    if not last_message.get("tool_calls"):
        state.response = "No tool call found in previous step."
        logger.error("No tool call in last message", session_id=state.session_id)
        errors.labels(node="tool_call").inc()
        return state

    try:
        for tool_call in last_message["tool_calls"]:
            function_name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])

            if function_name not in FUNCTION_MAP:
                logger.error("Invalid function call", session_id=state.session_id, function_name=function_name)
                errors.labels(node="tool_call").inc()
                state.messages.append({
                    "role": "function",
                    "name": function_name,
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps({"error": f"Invalid function {function_name}"})
                })
                continue

            try:
                result = await FUNCTION_MAP[function_name](**args)
                if function_name == "invalid":
                    state.response = result["error"]
                    state.messages.append({
                        "role": "function",
                        "name": function_name,
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result)
                    })
                    logger.info("Invalid query detected", session_id=state.session_id)
                    return state  # Route directly to output
                else:
                    state.messages.append({
                        "role": "function",
                        "name": function_name,
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result)
                    })
                    function_calls.labels(function_name=function_name).inc()
                    logger.info("Function call executed", session_id=state.session_id, function_name=function_name)
            except Exception as e:
                logger.error("Function call error", session_id=state.session_id, function_name=function_name,
                             error=str(e))
                errors.labels(node="tool_call").inc()
                state.messages.append({
                    "role": "function",
                    "name": function_name,
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps({"error": f"Error executing {function_name}: {str(e)}"})
                })

    except Exception as e:
        state.response = f"Error processing tool calls: {str(e)}"
        logger.error("Error in tool call node", session_id=state.session_id, error=str(e))
        errors.labels(node="tool_call").inc()
        return state

    state.iteration += 1
    return state

# Summarizer Node
async def summarizer_node(state: ChatState) -> ChatState:
    logger.info(
        "Entering summarizer node",
        session_id=state.session_id,
        model=state.llm_client["model"],
        api_base=state.llm_client["api_base"]
    )
    K = 2
    if len(state.messages) > 0:
        try:
            messages = [{"role": "system",
                         "content": f"Provide a concise summary (50-100 words) of the conversation, focusing on financial topics and key user queries. Previous summary {state.summary}. <previous-summary-end>"}] + state.messages[1:]
            summary_response = await call_llm(state, messages, temperature=0.5)
            state.summary = summary_response.choices[0].message.content
            logger.info("Summary updated", session_id=state.session_id, summary_length=len(state.summary))
        except Exception as e:
            logger.error("Error in summarizer node", session_id=state.session_id, error=str(e))
            errors.labels(node="summarizer").inc()
            state.summary = state.summary or ""
    else:
        logger.info("Skipping summarization", session_id=state.session_id, user_message_count=state.user_message_count)
    return state

# Output Node
async def output_node(state: ChatState) -> ChatState:
    logger.info("Entering output node", session_id=state.session_id)
    return state

# Workflow Builder
def build_workflow() -> CompiledStateGraph:
    workflow = StateGraph(ChatState)

    workflow.add_node("input", input_node)
    workflow.add_node("cot", cot_node)
    workflow.add_node("tool_call", tool_call_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("output", output_node)

    workflow.set_entry_point("input")
    workflow.add_edge("input", "cot")
    workflow.add_conditional_edges(
        "cot",
        lambda state: (
            "tool_call" if state.messages[-1].get("tool_calls") else
            "summarizer" if state.finish_reason == "stop" or state.response else
            "cot" if state.iteration < state.max_iterations else
            "output"
        )
    )
    workflow.add_conditional_edges(
        "tool_call",
        lambda state: (
            "output" if state.response or any(msg["name"] == "invalid" for msg in state.messages if msg.get("role") == "function") else
            "cot"
        )
    )
    workflow.add_edge("summarizer", "output")
    workflow.add_edge("output", END)

    return workflow.compile()

# Database Update Function
async def update_conversation_state(session: Conversation, state: ChatState, db: AsyncSession) -> None:
    logger.info("Updating conversation state", session_id=session.id)
    user_message = Message(
        conversation_id=session.id,
        role=RoleEnum.human,
        content=state['user_query'],
        timestamp=datetime.utcnow()
    )
    db.add(user_message)

    if state.get('response'):
        ai_message = Message(
            conversation_id=session.id,
            role=RoleEnum.ai,
            content=state.get('response'),
            timestamp=datetime.utcnow()
        )
        db.add(ai_message)

    session.summary = state['summary'] or session.summary
    session.updated_at = datetime.utcnow()

    await db.commit()

# FastAPI Endpoint
async def run_chat_graph(
        session: Conversation,
        user_message: str,
        user: User,
) -> ChatState:
    logger.info(
        "Running chat graph",
        session_id=str(session.id),
        user_id=str(user.id),
        model=session.llm_model,
        timestamp=datetime.utcnow().isoformat()
    )
    K = 10
    messages = []
    if session.messages is not None:
        messages = [
                       {"role": msg.role.value, "content": msg.content}
                       for msg in session.messages
                       if msg.role in [RoleEnum.human, RoleEnum.ai]
                   ][-K:]
    else:
        logger.warning("session.messages is None, initializing empty list", session_id=str(session.id))
    # todo: forcing to use this one for now.
    session.llm_model = "litellm_proxy/gemini-2.0-flash"
    provider = session.llm_model.split("/")[0]
    api_base = {
        "gemini": "https://generativelanguage.googleapis.com",
        "xai": "https://api.x.ai/v1",
        "litellm_proxy" : "http://localhost:4000"
    }.get(provider, "http://localhost:4000")

    workflow = build_workflow()
    state = ChatState(
        session_id=str(session.id),
        user_id=str(user.id),
        tier=user.tier,
        user_query=user_message,
        messages=messages,
        summary=session.summary or "",
        user_message_count=len([msg for msg in (session.messages or []) if msg.role == RoleEnum.human]) + 1,
        llm_client={
            "model": session.llm_model,
            "api_base": api_base,
            "api_key": os.getenv(f"{provider.upper()}_API_KEY", "sk-1234"),
            "metadata": {"user_id": str(user.id), "tier": user.tier}
        }
    )
    result = await workflow.ainvoke(state)
    # return {"output": result.get("response", "No response generated."), "state": result}
    return result