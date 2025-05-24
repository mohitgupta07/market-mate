import pytest
import pytest_asyncio
import aiohttp
import uuid
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

@pytest_asyncio.fixture
async def client():
    async with aiohttp.ClientSession() as session:
        yield session

@pytest_asyncio.fixture
async def auth_headers(client) -> Dict[str, str]:
    """Get authentication headers by registering and logging in a test user"""
    # Register a test user
    test_user = {
        "email": f"test_{uuid.uuid4()}@example.com",
        "password": "testpassword123",
        "is_active": True,
        "is_superuser": False,
        "is_verified": False,
        "full_name": "Test User"
    }
    
    await client.post(f"{BASE_URL}/auth/register", json=test_user)
      # Login - the cookie will be automatically handled by the client session
    login_data = {
        "username": test_user["email"],
        "password": test_user["password"]
    }
    response = await client.post(f"{BASE_URL}/auth/login", data=login_data)
    assert response.status == 204  # Success with no content
    
    return {}

@pytest.mark.asyncio
async def test_start_session(client, auth_headers):
    """Test creating a new chat session"""
    response = await client.post(f"{BASE_URL}/chat/start_session")
    assert response.status == 200
    data = await response.json()
    assert "session_id" in data
    return data["session_id"]

@pytest.mark.asyncio
async def test_chat_flow(client, auth_headers):
    """Test the complete chat flow"""
    session_id = await test_start_session(client, auth_headers)
    
    # Send a message
    message = "Hello, this is a test message!"
    response = await client.post(
        f"{BASE_URL}/chat/chat/{session_id}",
        params={"message": message}
    )
    assert response.status == 200
    data = await response.json()
    assert "reply" in data
    assert data["reply"] == f"MOCK RESPONSE: {message}"
    
    # Get session details
    response = await client.get(
        f"{BASE_URL}/chat/sessions/{session_id}"
    )
    assert response.status == 200
    data = await response.json()
    assert data["id"] == session_id
    assert len(data["messages"]) == 2  # User message and AI response
    
    # List all sessions
    response = await client.get(
        f"{BASE_URL}/chat/sessions"
    )
    assert response.status == 200
    data = await response.json()
    assert len(data) > 0
    assert any(session["id"] == session_id for session in data)
    
    # Restart session
    response = await client.post(
        f"{BASE_URL}/chat/restart_session/{session_id}"
    )
    assert response.status == 200
    data = await response.json()
    assert "new_session_id" in data
    new_session_id = data["new_session_id"]
    assert new_session_id != session_id
    
    # Resume old session
    response = await client.post(
        f"{BASE_URL}/chat/sessions/{session_id}/resume"
    )
    assert response.status == 200
    data = await response.json()
    assert data["message"] == "Session resumed successfully"

@pytest.mark.asyncio
async def test_invalid_session(client, auth_headers):
    """Test error handling for invalid session ID"""
    invalid_session_id = str(uuid.uuid4())
    response = await client.post(
        f"{BASE_URL}/chat/chat/{invalid_session_id}",
        params={"message": "This should fail"}
    )
    assert response.status == 404

@pytest.mark.asyncio
async def test_unauthorized_access(client):
    """Test that endpoints require authentication"""
    response = await client.post(f"{BASE_URL}/chat/start_session")
    assert response.status in (401, 403)  # Either unauthorized or forbidden
