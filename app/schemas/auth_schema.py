from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    email: str = Field(
        description="Email or username. You can login with either.",
        examples=["huynh2102", "huynh2102@gmail.com"],
    )
    password: str = Field(examples=["123456"])
