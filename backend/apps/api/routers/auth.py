"""Authentication endpoints: signup, login, refresh, logout, profile."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from apps.api.core.config import settings
from apps.api.core.deps import CurrentUser, DbSession, client_ip
from apps.api.models import User
from apps.api.schemas.auth import (
    AuthProviders,
    ExternalAccessTokenRequest,
    ExternalAuthResult,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
)
from apps.api.schemas.user import UserPublic, UserUpdate
from apps.api.services import external_auth
from apps.api.services.auth import (
    TokenError,
    create_access_token,
    create_login_ticket,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from apps.api.services.rate_limit import login_rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def _issue_tokens(user: User) -> TokenPair:
    claims = {"email": user.email, "role": user.role}
    return TokenPair(
        access_token=create_access_token(user.id, extra_claims=claims),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRES_IN,
        user=UserPublic.model_validate(user),
    )


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession) -> TokenPair:
    """Register a new account and return a token pair."""
    email = _normalise_email(payload.email)

    existing = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing is not None:
        # 409 rather than a generic 400 so clients can branch on it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name,
        role="USER",
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _issue_tokens(user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenPair:
    """Exchange email + password for a token pair."""
    email = _normalise_email(payload.email)
    limiter_key = f"{email}|{client_ip(request)}"

    if not login_rate_limiter.check(limiter_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(login_rate_limiter.retry_after(limiter_key))},
        )

    user = db.scalar(select(User).where(func.lower(User.email) == email))

    # Always run a verification so a missing user and a wrong password take a
    # comparable amount of time, and return the same message either way.
    password_ok = verify_password(payload.password, user.password_hash if user else "")

    if user is None or not password_ok:
        login_rate_limiter.register_failure(limiter_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    login_rate_limiter.reset(limiter_key)
    return _issue_tokens(user)


@router.get("/providers", response_model=AuthProviders)
def auth_providers() -> AuthProviders:
    """Public capability probe used by the login page."""
    supabase_problem = external_auth.supabase_configuration_error()
    google_problem = external_auth.google_configuration_error()
    return AuthProviders(
        supabase_email=supabase_problem is None,
        google=google_problem is None,
        detail={"supabase_email": supabase_problem, "google": google_problem},
    )


def _external_error(exc: external_auth.ExternalAuthError, status_code: int) -> HTTPException:
    if isinstance(exc, external_auth.ExternalAuthNotConfigured):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HTTPException(status_code=status_code, detail=str(exc))


async def _tokens_from_supabase(
    access_token: str, db: DbSession
) -> TokenPair:
    profile = await external_auth.supabase_user(access_token)
    return _issue_tokens(external_auth.sync_local_user(db, profile))


@router.post("/supabase/login", response_model=ExternalAuthResult)
async def supabase_login(
    payload: LoginRequest, request: Request, db: DbSession
) -> ExternalAuthResult:
    """Verify email/password with Supabase, then issue HydraClip API tokens."""
    email = _normalise_email(payload.email)
    limiter_key = f"supabase:{email}|{client_ip(request)}"
    if not login_rate_limiter.check(limiter_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(login_rate_limiter.retry_after(limiter_key))},
        )
    try:
        session = await external_auth.supabase_password_login(email, payload.password)
        tokens = await _tokens_from_supabase(session["access_token"], db)
    except external_auth.ExternalAuthError as exc:
        login_rate_limiter.register_failure(limiter_key)
        raise _external_error(exc, status.HTTP_401_UNAUTHORIZED) from exc
    login_rate_limiter.reset(limiter_key)
    return ExternalAuthResult(
        authenticated=True,
        message="Signed in with Supabase.",
        tokens=tokens,
    )


@router.post("/supabase/signup", response_model=ExternalAuthResult)
async def supabase_email_signup(
    payload: SignupRequest, db: DbSession
) -> ExternalAuthResult:
    """Create a Supabase email account and honor email-confirmation settings."""
    try:
        result = await external_auth.supabase_signup(
            _normalise_email(payload.email), payload.password, payload.name
        )
        access_token = result.get("access_token")
        if access_token:
            tokens = await _tokens_from_supabase(access_token, db)
            return ExternalAuthResult(
                authenticated=True,
                message="Account created and signed in.",
                tokens=tokens,
            )
    except external_auth.ExternalAuthError as exc:
        raise _external_error(exc, status.HTTP_400_BAD_REQUEST) from exc

    return ExternalAuthResult(
        authenticated=False,
        requires_email_confirmation=True,
        message="Check your email to confirm the account, then sign in.",
    )


@router.post("/supabase/exchange", response_model=ExternalAuthResult)
async def supabase_exchange(
    payload: ExternalAccessTokenRequest, db: DbSession
) -> ExternalAuthResult:
    """Exchange a Supabase session (including social login) for app tokens."""
    try:
        tokens = await _tokens_from_supabase(payload.access_token, db)
    except external_auth.ExternalAuthError as exc:
        raise _external_error(exc, status.HTTP_401_UNAUTHORIZED) from exc
    return ExternalAuthResult(
        authenticated=True,
        message="Supabase session accepted.",
        tokens=tokens,
    )


@router.get("/google/authorize")
def google_authorize() -> dict[str, str]:
    """Start Google OIDC using the OAuth client already used for YouTube."""
    try:
        return {"authorize_url": external_auth.google_authorize_url()}
    except external_auth.ExternalAuthError as exc:
        raise _external_error(exc, status.HTTP_503_SERVICE_UNAVAILABLE) from exc


def _google_finish(*, error: str | None = None) -> RedirectResponse:
    query = urlencode({"provider": "google", **({"error": error} if error else {})})
    return RedirectResponse(
        f"{settings.APP_URL.rstrip('/')}/auth/callback?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/google/callback")
async def google_callback(
    db: DbSession,
    code: str | None = Query(default=None),
    state_value: str | None = Query(default=None, alias="state"),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    """Complete Google OIDC and set a short-lived HttpOnly exchange ticket."""
    if error or not code:
        return _google_finish(error=error_description or error or "Google returned no code.")
    try:
        profile = await external_auth.google_identity(code, state_value or "")
        user = external_auth.sync_local_user(db, profile)
    except external_auth.ExternalAuthError as exc:
        return _google_finish(error=str(exc))

    response = _google_finish()
    response.set_cookie(
        key="hydraclip_google_login",
        value=create_login_ticket(user.id),
        max_age=settings.GOOGLE_LOGIN_TICKET_SECONDS,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )
    return response


@router.post("/google/exchange", response_model=TokenPair)
def google_exchange(request: Request, response: Response, db: DbSession) -> TokenPair:
    """Consume the HttpOnly callback ticket and return normal app tokens."""
    ticket = request.cookies.get("hydraclip_google_login")
    if not ticket:
        raise HTTPException(status_code=401, detail="Google login ticket is missing.")
    try:
        claims = decode_token(ticket, expected_type="login_ticket")
        user = db.get(User, int(claims["sub"]))
    except (TokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Google login ticket is invalid.") from exc
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Google account is no longer active.")
    response.delete_cookie("hydraclip_google_login", path="/")
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    """Exchange a valid refresh token for a new token pair."""
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is no longer active.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _issue_tokens(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def logout(_: CurrentUser) -> Response:
    """Log out.

    Tokens are stateless, so this only confirms the caller was authenticated;
    the client is responsible for discarding them. A server-side deny-list
    belongs here once Redis is wired up.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserPublic)
def read_me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserPublic)
def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> User:
    if payload.name is not None:
        user.name = payload.name
    db.commit()
    db.refresh(user)
    return user
