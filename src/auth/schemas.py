from typing import Optional
from fastapi_users import schemas

class UserRead(schemas.BaseUser[int]):
    full_name: Optional[str]

class UserCreate(schemas.BaseUserCreate):
    full_name: Optional[str]

class UserUpdate(schemas.BaseUserUpdate):
    full_name: Optional[str]
