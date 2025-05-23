#pip install fastapi uvicorn nest_asyncio itsdangerous python-multipart
from fastapi import FastAPI, Request, Response, Form, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uuid
from itsdangerous import URLSafeSerializer
import uvicorn


app = FastAPI()

# In-memory session store (session_id → username)
session_store = {}

# Secure serializer for cookies
SECRET_KEY = "super-secret-key"  # Replace with env variable in prod
serializer = URLSafeSerializer(SECRET_KEY)

SESSION_COOKIE_NAME = "session_id"


async def authenticate_user(username, password):
    if username == "admin" and password == "password":
        return True
    else:
        return False


@app.post("/login")
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    user = await authenticate_user(username, password)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": "Invalid username or password"},
        )
    # 2. Create session ID
    session_id = str(uuid.uuid4())
    session_store[session_id] = username
    # 3. Sign it and set in cookie
    signed_session = serializer.dumps(session_id)
    response.set_cookie(key=SESSION_COOKIE_NAME, value=signed_session, httponly=True)

    return {"message": "Login successful", "username": username}


@app.get("/me")
async def get_current_user(request: Request):
  # 1. Read signed session ID from cookie
  signed_session = request.cookies.get(SESSION_COOKIE_NAME)
  if not signed_session:
      raise HTTPException(status_code=401, detail="Not logged in")

  try:
      session_id = serializer.loads(signed_session)
      username = session_store.get(session_id)
      if not username:
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
  except Exception:
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cookie or session")

  return {"username": username}



uvicorn.run(app, host="127.0.0.1", port=8000)