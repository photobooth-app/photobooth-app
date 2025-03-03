import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel

from ..appconfig import appconfig

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str


class User(BaseModel):
    username: str
    full_name: str | None = None
    # disabled: Union[bool, None] = None # functionality not used currently.


class UserInDB(User):
    # hashed_password: str
    password: str


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/token")


def verify_password(plain_password: str, password: str):
    return secrets.compare_digest(plain_password.encode("utf8"), password.encode("utf8"))


def get_users() -> dict[str, UserInDB]:
    users_db = {
        "admin": UserInDB(
            username="admin",
            full_name="Admin",
            password=appconfig.common.admin_password.get_secret_value(),
        )
    }

    return users_db


def get_user(db: dict[str, UserInDB], user_id: str) -> UserInDB | None:
    if user_id in db:
        return db[user_id]


def authenticate_user(users_db, user_id: str, password: str):
    user = get_user(users_db, user_id)
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, appconfig.misc.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, appconfig.misc.secret_key, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    user = get_user(get_users(), user_id=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
