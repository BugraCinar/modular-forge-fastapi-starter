import httpx

from modular_forge.shared.errors import DomainError, unavailable


def verify_captcha(settings, token: str | None):
    if not settings.recaptcha_enabled:
        return
    if not token:
        raise DomainError(400, "captcha_required", "CAPTCHA verification is required.")
    try:
        response = httpx.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": settings.recaptcha_secret_key, "response": token},
            timeout=5,
        )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError):
        raise unavailable() from None
    if (
        not result.get("success")
        or result.get("hostname") != settings.recaptcha_expected_hostname
        or result.get("action") != settings.recaptcha_expected_action
        or result.get("score", 0) < settings.recaptcha_score_threshold
    ):
        raise DomainError(400, "captcha_invalid", "CAPTCHA verification failed.")
