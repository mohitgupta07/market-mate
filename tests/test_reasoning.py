import pytest
import pytest_asyncio
import json
from datetime import datetime
from src.chat.reasoning import run_chat_graph
from src.auth.models import RoleEnum

# Mock dependencies
@pytest_asyncio.fixture
async def mock_conversation():
    class MockConversation:
        id = "test-session-123"
        llm_model = "gemini/gemini-2.0-flash"
        messages = []
        summary = ""
        updated_at = datetime.utcnow()
    return MockConversation()

@pytest_asyncio.fixture
async def mock_user():
    class MockUser:
        id = "test-user-123"
        tier = "free"
    return MockUser()

@pytest_asyncio.fixture
async def mock_db():
    class MockAsyncSession:
        async def add(self, obj):
            pass
        async def commit(self):
            pass
    return MockAsyncSession()

@pytest_asyncio.fixture
async def mock_functions(monkeypatch):
    async def mock_get_quarterly_results(company_name: str, quarter: str) -> dict:
        return {
            "company_name": company_name,
            "quarter": quarter,
            "sales": 90000000
        }

    async def mock_get_stock_price(company_name: str) -> dict:
        return {
            "company_name": company_name,
            "price": 150.25
        }

    function_map = {
        "get_quarterly_results": mock_get_quarterly_results,
        "get_stock_price": mock_get_stock_price
    }
    functions = [
        {
            "type": "function",
            "function": {
                "name": "get_quarterly_results",
                "description": "Fetch quarterly financial results for a company",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"},
                        "quarter": {
                            "type": "string",
                            "description": "Quarter in YYYY-Q# format (e.g., 2024-Q4)"
                        }
                    },
                    "required": ["company_name", "quarter"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_stock_price",
                "description": "Fetch current stock price for a company",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string"}
                    },
                    "required": ["company_name"]
                }
            }
        }
    ]

    monkeypatch.setattr("src.chat.functions_list.FUNCTION_MAP", function_map)
    monkeypatch.setattr("src.chat.functions_list.FUNCTIONS", functions)
    return function_map, functions

@pytest_asyncio.fixture
async def mock_prompts(monkeypatch):
    system_prompt = "You are a financial assistant. Respond to queries about stocks, earnings, or financial news."
    reasoning_prompt_template = "Reason through the query: {user_query}\nAvailable functions:\n{functions_list}"
    monkeypatch.setattr("src.chat.prompt.SYSTEM_PROMPT", system_prompt)
    monkeypatch.setattr("src.chat.prompt.REASONING_PROMPT_TEMPLATE", reasoning_prompt_template)
    return system_prompt, reasoning_prompt_template

# Tests
@pytest.mark.asyncio
async def test_multiple_tool_calls(mock_conversation, mock_user, mock_db, mock_functions, mock_prompts):
    query = "Get Apple's sales for 2024-Q4 and current stock price"
    result = await run_chat_graph(mock_conversation, query, mock_user)
    assert result["output"] is not None
    assert any(msg["role"] == "function" and msg["name"] == "get_quarterly_results" for msg in result["state"].messages)
    assert any(msg["role"] == "function" and msg["name"] == "get_stock_price" for msg in result["state"].messages)
    print(f"Test 1 - Multiple tool calls:\nQuery: {query}\nResponse: {result['output']}\nMessages: {json.dumps(result['state'].messages, indent=2)}")

@pytest.mark.asyncio
async def test_clarification_request(mock_conversation, mock_user, mock_db, mock_functions, mock_prompts):
    query = "What were Apple's sales last quarter?"
    result = await run_chat_graph(mock_conversation, query, mock_user)
    assert "specify" in result["output"].lower() or "clarify" in result["output"].lower()
    assert result["state"].finish_reason == "stop"
    assert not any(msg.get("tool_calls") for msg in result["state"].messages)
    print(f"Test 2 - Clarification request:\nQuery: {query}\nResponse: {result['output']}\nMessages: {json.dumps(result['state'].messages, indent=2)}")