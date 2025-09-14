from typing import Optional
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class TokenPayload(BaseModel):
    sub: Optional[str] = None

class EClassAuthRequest(BaseModel):
    eclass_username: str
    eclass_password: str

class EClassUser(BaseModel):
    id: str
    username: str
    eclass_username: str
    created_at: str

class EClassToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: EClassUser

class EClassTokenRefresh(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    eclass_username: str
    eclass_password: str

class UserLogin(BaseModel):
    eclass_username: str
    eclass_password: str

class UserOut(BaseModel):
    id: str
    eclass_username: Optional[str] = None