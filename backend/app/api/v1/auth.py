import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import bearer_token, current_user, get_session
from app.db.models import User
from app.services import auth as service

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginInput(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    name: str
    role: Literal["admin", "manager", "analyst"]


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginInput, session: Annotated[AsyncSession, Depends(get_session)]):
    token, user = await service.login(session, body.email, body.password.get_secret_value())
    return LoginResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(current_user)]):
    return user


@router.post("/logout", status_code=204)
async def logout(
    user: Annotated[User, Depends(current_user)],
    token: Annotated[str, Depends(bearer_token)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await service.logout(session, token, user)
    return Response(status_code=204)
