import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from auth.database import engine, Base
from auth.users import fastapi_users, auth_backend
from auth.schemas import UserRead, UserCreate, UserUpdate
from auth.models import User  # Important: import models to ensure they're registered with Base
from chat import router as chat_router

# Create app and routes
app = FastAPI()

origins = [
    "http://localhost", # Your frontend's origin if served from a different port
    "http://localhost:3000", # Example if using React dev server
    "http://localhost:5173", # Example if using Vite dev server
    "http://127.0.0.1:5500", # Example if using VS Code Live Server
    # Add the specific origin your frontend is running on
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows specific origins
    allow_credentials=True, # Allows cookies to be included in requests
    allow_methods=["*"],    # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],    # Allows all headers
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(user_schema=UserRead, user_create_schema=UserCreate), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_users_router(user_schema=UserRead, user_update_schema=UserUpdate), prefix="/users", tags=["users"]
)

# Include chat routes
app.include_router(chat_router, prefix="/chat", tags=["chat"])

@app.get("/protected")
async def protected_route(user: UserRead = Depends(fastapi_users.current_user())):
    return {"message": f"Hello {user.email}"}

# DB setup on startup 
# using this as it lets swagger work at localhost:8000/docs
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)