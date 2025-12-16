from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


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

    @field_validator("email")
    @classmethod
    def _normalize_identifier(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("email must not be empty")
        return v
