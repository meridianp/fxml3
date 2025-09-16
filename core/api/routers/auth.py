"""
Authentication API endpoints.

This module provides authentication endpoints including login, logout, and token refresh.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.auth_enhanced import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_client_ip,
    get_current_user,
)
from fxml4.api.auth.database import get_db
from fxml4.api.auth.models import User
from fxml4.api.auth.service import AuthenticationService
from fxml4.api.auth.totp_manager import TwoFactorMethod, totp_manager

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["authentication"],
    responses={404: {"description": "Not found"}},
)


# Pydantic models
class Token(BaseModel):
    """Token response model."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int
    requires_2fa: bool = False


class TwoFactorRequest(BaseModel):
    """Two-factor authentication request."""

    session_token: str
    totp_code: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class TwoFactorSetupResponse(BaseModel):
    """2FA setup response with QR code."""

    secret: str
    qr_code_svg: str
    qr_code_data_url: str
    backup_codes: List[str]
    provisioning_uri: str


class TwoFactorEnableRequest(BaseModel):
    """Request to enable 2FA."""

    totp_code: str


class TwoFactorStatusResponse(BaseModel):
    """2FA status response."""

    enabled: bool
    setup_complete: bool
    backup_codes_remaining: int
    last_used: Optional[str] = None
    method_used: Optional[str] = None


class BackupCodesResponse(BaseModel):
    """Backup codes response."""

    backup_codes: List[str]
    codes_remaining: int


# Session storage for 2FA (in production, use Redis or similar)
pending_2fa_sessions = {}


@router.post("/token", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth2 compatible token login endpoint.

    Returns access token and refresh token.
    If 2FA is enabled, returns a session token instead.
    """
    # Authenticate user
    user = await authenticate_user(form_data, request, db)

    # Check if 2FA is required
    if user.totp_enabled:
        # Generate temporary session token
        session_token = AuthenticationService.create_access_token(
            {"sub": str(user.id), "type": "2fa_pending"},
            expires_delta=timedelta(minutes=5),
        )

        # Store session (in production, use Redis)
        pending_2fa_sessions[session_token] = {
            "user_id": str(user.id),
            "expires": datetime.now(timezone.utc) + timedelta(minutes=5),
        }

        return Token(
            access_token=session_token,
            token_type="2fa_pending",
            expires_in=300,  # 5 minutes
            requires_2fa=True,
        )

    # Generate tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    # Log successful login
    await AuthenticationService._log_auth_event(
        db,
        user.id,
        "token_issued",
        True,
        {"token_type": "password_auth"},
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    await db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        requires_2fa=False,
    )


@router.post("/token/2fa", response_model=Token)
async def verify_2fa_login(
    request: Request, two_fa_data: TwoFactorRequest, db: AsyncSession = Depends(get_db)
):
    """
    Complete login with 2FA verification.
    """
    # Verify session token
    session_data = pending_2fa_sessions.get(two_fa_data.session_token)

    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # Check expiry
    if datetime.now(timezone.utc) > session_data["expires"]:
        del pending_2fa_sessions[two_fa_data.session_token]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        )

    # Verify 2FA code
    user_id = session_data["user_id"]
    if not await AuthenticationService.verify_2fa(db, user_id, two_fa_data.totp_code):
        await AuthenticationService._log_auth_event(
            db,
            user_id,
            "2fa_failed",
            False,
            {},
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
        )
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code"
        )

    # Get user
    from sqlalchemy import select

    from .models import User

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    # Generate tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    # Clean up session
    del pending_2fa_sessions[two_fa_data.session_token]

    # Log successful login
    await AuthenticationService._log_auth_event(
        db,
        user.id,
        "token_issued",
        True,
        {"token_type": "2fa_auth"},
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    await db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        requires_2fa=False,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token.
    """
    try:
        # Decode refresh token
        from jose import JWTError, jwt

        from fxml4.api.auth.auth_enhanced import ALGORITHM, SECRET_KEY

        payload = jwt.decode(
            refresh_data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM]
        )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

        # Get user
        from sqlalchemy import select

        from .models import User

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Generate new access token
        access_token = create_access_token(user)

        # Log token refresh
        await AuthenticationService._log_auth_event(
            db,
            user.id,
            "token_refreshed",
            True,
            {},
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
        )
        await db.commit()

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            requires_2fa=False,
        )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Logout current user.

    Note: Since we use stateless JWTs, this endpoint primarily
    logs the logout event. In production, you might want to:
    - Maintain a token blacklist
    - Clear client-side tokens
    - Invalidate refresh tokens
    """
    # Log logout event
    await AuthenticationService._log_auth_event(
        db,
        current_user.id,
        "logout",
        True,
        {},
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )

    # Clear session token if stored
    if current_user.session_token:
        current_user.session_token = None

    await db.commit()

    # Clear cookies if used
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.

    This is a convenience endpoint that duplicates /api/v1/users/me
    for authentication testing.
    """
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "roles": [role.name for role in current_user.roles],
    }


# ===== 2FA MANAGEMENT ENDPOINTS =====


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Set up Two-Factor Authentication for the current user.

    Returns QR code and backup codes for TOTP setup.
    """
    try:
        setup_result = await totp_manager.setup_totp(db, str(current_user.id))

        return TwoFactorSetupResponse(
            secret=setup_result.secret,
            qr_code_svg=setup_result.qr_code_svg,
            qr_code_data_url=setup_result.qr_code_data_url,
            backup_codes=setup_result.backup_codes,
            provisioning_uri=setup_result.provisioning_uri,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/2fa/enable")
async def enable_2fa(
    request: Request,
    enable_data: TwoFactorEnableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Enable Two-Factor Authentication by verifying TOTP code.
    """
    client_ip = get_client_ip(request)

    success = await totp_manager.verify_and_enable_totp(
        db, str(current_user.id), enable_data.totp_code, client_ip
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code"
        )

    return {"message": "Two-factor authentication enabled successfully"}


@router.post("/2fa/disable")
async def disable_2fa(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Disable Two-Factor Authentication for the current user.
    """
    client_ip = get_client_ip(request)

    success = await totp_manager.disable_totp(db, str(current_user.id), client_ip)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to disable 2FA"
        )

    return {"message": "Two-factor authentication disabled successfully"}


@router.get("/2fa/status", response_model=TwoFactorStatusResponse)
async def get_2fa_status(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get Two-Factor Authentication status for the current user.
    """
    status_info = await totp_manager.get_2fa_status(db, str(current_user.id))

    return TwoFactorStatusResponse(
        enabled=status_info.enabled,
        setup_complete=status_info.setup_complete,
        backup_codes_remaining=status_info.backup_codes_remaining,
        last_used=status_info.last_used.isoformat() if status_info.last_used else None,
        method_used=status_info.method_used.value if status_info.method_used else None,
    )


@router.post("/2fa/backup-codes", response_model=BackupCodesResponse)
async def generate_backup_codes(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate new backup codes for Two-Factor Authentication.

    Note: This will invalidate all existing backup codes.
    """
    try:
        backup_codes = await totp_manager.generate_new_backup_codes(
            db, str(current_user.id)
        )

        return BackupCodesResponse(
            backup_codes=backup_codes, codes_remaining=len(backup_codes)
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ===== ENHANCED 2FA LOGIN FLOW =====


@router.post("/token/2fa-enhanced", response_model=Token)
async def verify_2fa_login_enhanced(
    request: Request, two_fa_data: TwoFactorRequest, db: AsyncSession = Depends(get_db)
):
    """
    Complete login with enhanced 2FA verification using the TOTP manager.

    This replaces the basic /token/2fa endpoint with improved session management.
    """
    client_ip = get_client_ip(request)

    # Get 2FA session
    session = totp_manager.get_2fa_session(two_fa_data.session_token)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    # Verify 2FA token
    success, method = await totp_manager.verify_2fa_token(
        db, session.user_id, two_fa_data.totp_code, client_ip
    )

    if not success:
        # Increment attempt counter
        remaining_attempts = totp_manager.increment_2fa_attempt(
            two_fa_data.session_token
        )

        if remaining_attempts is None:
            detail = "Maximum attempts exceeded. Please login again."
        else:
            detail = f"Invalid verification code. {3 - remaining_attempts} attempts remaining."

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    # Get user
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one()

    # Generate tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    # Clean up session
    totp_manager.delete_2fa_session(two_fa_data.session_token)

    # Log successful login
    await AuthenticationService._log_auth_event(
        db,
        user.id,
        "token_issued",
        True,
        {"token_type": "2fa_auth", "2fa_method": method.value if method else "unknown"},
        client_ip,
        request.headers.get("user-agent"),
    )
    await db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        requires_2fa=False,
    )


# ===== ENHANCED LOGIN WITH IMPROVED 2FA SESSION =====


@router.post("/token-enhanced", response_model=Token)
async def login_enhanced(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Enhanced OAuth2 compatible token login endpoint with improved 2FA session management.

    Returns access token and refresh token.
    If 2FA is enabled, returns a session token for 2FA verification.
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    # Authenticate user
    user = await authenticate_user(form_data, request, db)

    # Check if 2FA is required
    if user.totp_enabled:
        # Create 2FA session using TOTP manager
        session_token = totp_manager.create_2fa_session(
            user_id=str(user.id), client_ip=client_ip, user_agent=user_agent
        )

        return Token(
            access_token=session_token,
            token_type="2fa_pending",
            expires_in=300,  # 5 minutes
            requires_2fa=True,
        )

    # Generate tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    # Log successful login
    await AuthenticationService._log_auth_event(
        db,
        user.id,
        "token_issued",
        True,
        {"token_type": "password_auth"},
        client_ip,
        user_agent,
    )
    await db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        requires_2fa=False,
    )


# Import required constants
from fxml4.api.auth.auth_enhanced import ACCESS_TOKEN_EXPIRE_MINUTES
