from fastapi_users import FastAPIUsers
from fastapi_users.manager import BaseUserManager
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users.authentication import CookieTransport, AuthenticationBackend, JWTStrategy
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal
from .models import User
from .schemas import UserRead, UserCreate, UserUpdate

SECRET = "SUPERSECRETKEY"

# Dependency
async def get_async_session() -> AsyncGenerator[SessionLocal, None]:
    async with SessionLocal() as session:
        yield session

# Adapter
async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)

# Auth backend
cookie_transport = CookieTransport(cookie_name="auth", cookie_max_age=3600)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

class UserManager(BaseUserManager[User, int]):
    user_db_model = User
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    def __init__(self, user_db: SQLAlchemyUserDatabase):
        super().__init__(user_db)

    def parse_id(self, value: str) -> int:
        return int(value)

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

# FastAPI Users setup
fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)
