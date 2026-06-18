from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user_model import User
from app.schemas.api_key_schema import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services.api_key_service import (
    create_api_key,
    list_user_api_keys,
    revoke_api_key,
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row, plaintext = create_api_key(
        db,
        user=current_user,
        name=payload.name,
        expires_at=payload.expires_at,
        scopes=payload.scopes,
    )
    out = ApiKeyOut.model_validate(row).model_dump()
    return ApiKeyCreated(**out, plaintext_key=plaintext)


@router.get("", response_model=list[ApiKeyOut])
def list_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [ApiKeyOut.model_validate(k) for k in list_user_api_keys(db, current_user)]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = revoke_api_key(db, current_user, key_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or already revoked",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
