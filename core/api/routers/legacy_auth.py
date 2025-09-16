"""
Legacy authentication routes for backward compatibility.

This module provides the authentication routes that were previously
defined in main.py to maintain backward compatibility.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from fxml4.api.auth.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    USERS_DB,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)
from fxml4.api.schemas import Token, User

# Create router
router = APIRouter()


@router.post("/token", response_model=Token, tags=["authentication"])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None
):
    """Login to get an access token.

    Args:
        form_data: Form with username and password

    Returns:
        Access token
    """
    user = authenticate_user(USERS_DB, form_data.username, form_data.password, request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes},
        expires_delta=access_token_expires,
        request=request,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=User, tags=["authentication"])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get the current user.

    Args:
        current_user: Current user from token

    Returns:
        User information
    """
    return current_user
