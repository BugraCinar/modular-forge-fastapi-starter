import hmac

from fastapi import APIRouter, Depends, Request, Response

from modular_forge.auth.schemas import (
    ChangePasswordRequest,
    EmailRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
    TwoFactorLoginRequest,
)
from modular_forge.security.dependencies import current_account, runtime
from modular_forge.shared.errors import DomainError, unauthorized

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
ACCEPTED = {"message": "If the account is eligible, an email will be sent."}


def cookie_names(settings):
    prefix = "__Host-" if settings.cookie_secure else ""
    return prefix + "forge_refresh", prefix + "forge_csrf"


def csrf_value(rt):
    nonce = rt.security.opaque_token()
    return nonce + "." + rt.security.token_hash(nonce, purpose="csrf")


def set_session_cookie(rt, response, session):
    refresh, csrf = cookie_names(rt.settings)
    response.set_cookie(
        refresh,
        session["refresh_token"],
        httponly=True,
        secure=rt.settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=rt.settings.refresh_token_seconds,
    )
    response.set_cookie(
        csrf,
        csrf_value(rt),
        httponly=False,
        secure=rt.settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=rt.settings.refresh_token_seconds,
    )
    return {**session, "refresh_token": None}


def request_refresh_token(rt, request, body):
    refresh, csrf = cookie_names(rt.settings)
    if raw := request.cookies.get(refresh):
        cookie, header = request.cookies.get(csrf, ""), request.headers.get("x-xsrf-token", "")
        nonce, separator, signature = cookie.partition(".")
        origin = request.headers.get("origin")
        if (
            not cookie
            or not hmac.compare_digest(cookie, header)
            or not separator
            or not hmac.compare_digest(signature, rt.security.token_hash(nonce, purpose="csrf"))
            or (origin and origin not in rt.settings.cors_allowed_origins)
        ):
            raise DomainError(403, "csrf_failed", "CSRF verification failed.")
        return raw, True
    if body and body.refresh_token:
        return body.refresh_token, False
    raise unauthorized()


@router.get("/csrf")
def csrf(response: Response, rt=Depends(runtime)):
    _, name = cookie_names(rt.settings)
    token = csrf_value(rt)
    response.set_cookie(
        name, token, secure=rt.settings.cookie_secure, samesite="lax", path="/", max_age=3600
    )
    return {"csrf_token": token}


@router.post("/register", status_code=202)
def register(data: RegisterRequest, rt=Depends(runtime)):
    rt.auth.register(data)
    return ACCEPTED


@router.post("/login")
def login(data: LoginRequest, response: Response, rt=Depends(runtime)):
    result = rt.auth.login(data)
    return (
        set_session_cookie(rt, response, result)
        if data.use_cookie and "refresh_token" in result
        else result
    )


@router.post("/two-factor")
def two_factor(data: TwoFactorLoginRequest, response: Response, rt=Depends(runtime)):
    result = rt.auth.complete_two_factor(data.challenge, data.code)
    return set_session_cookie(rt, response, result) if data.use_cookie else result


@router.post("/refresh")
def refresh(
    request: Request, response: Response, data: RefreshRequest | None = None, rt=Depends(runtime)
):
    raw, cookie = request_refresh_token(rt, request, data)
    result = rt.auth.refresh(raw)
    return set_session_cookie(rt, response, result) if cookie else result


@router.post("/logout", status_code=204)
def logout(request: Request, data: RefreshRequest | None = None, rt=Depends(runtime)):
    raw, _ = request_refresh_token(rt, request, data)
    rt.auth.logout(raw)
    response = Response(status_code=204)
    for name in cookie_names(rt.settings):
        response.delete_cookie(name, path="/", secure=rt.settings.cookie_secure, samesite="lax")
    return response


@router.post("/verify-email")
def verify_email(data: TokenRequest, rt=Depends(runtime)):
    rt.auth.verify_email(data.token)
    return {"message": "Email verified."}


@router.post("/resend-verification", status_code=202)
def resend_verification(data: EmailRequest, rt=Depends(runtime)):
    rt.auth.request_email(data.email, "verify")
    return ACCEPTED


@router.post("/forgot-password", status_code=202)
def forgot_password(data: EmailRequest, rt=Depends(runtime)):
    rt.auth.request_email(data.email, "reset")
    return ACCEPTED


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, rt=Depends(runtime)):
    rt.auth.reset_password(data.token, data.password)
    return {"message": "Password reset. Sign in again."}


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest, account=Depends(current_account), rt=Depends(runtime)
):
    rt.auth.change_password(account, data.password, data.new_password)
    return {"message": "Password changed. Sign in again."}


@router.get("/sessions")
def sessions(account=Depends(current_account), rt=Depends(runtime)):
    return rt.auth.sessions(account)


@router.delete("/sessions/{identifier}", status_code=204)
def revoke_session(identifier: str, account=Depends(current_account), rt=Depends(runtime)):
    rt.auth.revoke_session(account, identifier)


@router.post("/confirm-email-change")
def confirm_email_change(data: TokenRequest, rt=Depends(runtime)):
    rt.auth.confirm_email_change(data.token)
    return {"message": "Email changed. Sign in again."}
