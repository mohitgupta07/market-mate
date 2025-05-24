from typing import Dict, Any, List, Tuple, Annotated, Sequence, TypedDict
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, Graph
from langchain_core.runnables import RunnableConfig
from langchain_core.outputs import ChatResult, ChatGeneration

class MockLLM(BaseChatModel):
    def _generate(self, messages: List[BaseMessage], stop: List[str] | None = None, run_manager: Any | None = None, **kwargs) -> ChatResult:
        last_message = messages[-1].content
        response = f"MOCK RESPONSE: {last_message}"
        generation = ChatGeneration(message=AIMessage(content=response))
        return ChatResult(generations=[generation])
        
    @property
    def _llm_type(self) -> str:
        return "mock"

class AgentState(TypedDict):
    messages: List[BaseMessage]

def create_graph() -> Graph:
    # Create mock LLM
    mock_llm = MockLLM()

    # Create graph
    workflow = Graph()    # Define the agent processing logic
    def agent_node(state: AgentState) -> Dict:
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}
            
        if not isinstance(messages[-1], BaseMessage):
            # If we got a tuple or string, convert to HumanMessage
            last_message = messages[-1]
            if isinstance(last_message, tuple):
                message_content = last_message[1] if len(last_message) > 1 else str(last_message[0])
            else:
                message_content = str(last_message)
            messages[-1] = HumanMessage(content=message_content)
        
        # Generate response using the mock LLM
        messages_for_llm = [messages[-1]] if len(messages) == 1 else messages
        result = mock_llm.generate([messages_for_llm])
        new_message = result.generations[0][0].message
        messages.append(new_message)
        return {"messages": messages}

    # Define end node that preserves state
    def end_node(state: Dict) -> Dict:
        return state

    # Add nodes to the graph
    workflow.add_node("agent", agent_node)
    workflow.set_entry_point("agent")
    workflow.add_node("end", end_node)
    workflow.add_edge("agent", "end")

    # Compile the graph
    return workflow.compile()

def process_message(message: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """Process a message through the graph"""
    # Convert history to BaseMessage format
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    
    # Add current message
    messages.append(HumanMessage(content=message))
    
    # Create initial state
    state = {"messages": messages}    # Run the graph
    graph = create_graph()
    result = graph.invoke(state, {"config": {}}) or {"messages": []}
    
    # Extract the assistant's response
    final_messages = result.get("messages", [])
    assistant_message = final_messages[-1].content if final_messages else ""
    
    # Convert messages back to dict format for storage
    new_history = []
    for msg in final_messages:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        new_history.append({"role": role, "content": msg.content})
    
    return {
        "output": assistant_message,
        "history": new_history
    }

# Global instance
graph = process_message
