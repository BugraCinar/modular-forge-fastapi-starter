from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(Input):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=1024)
    captcha: str | None = Field(default=None, max_length=4096)


class LoginRequest(Input):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
    captcha: str | None = Field(default=None, max_length=4096)
    use_cookie: bool = False


class TokenRequest(Input):
    token: str = Field(min_length=20, max_length=256)


class RefreshRequest(Input):
    refresh_token: str | None = Field(default=None, min_length=20, max_length=256)


class EmailRequest(Input):
    email: EmailStr


class ResetPasswordRequest(TokenRequest):
    password: str = Field(min_length=12, max_length=1024)


class PasswordRequest(Input):
    password: str = Field(min_length=1, max_length=1024)


class ChangePasswordRequest(PasswordRequest):
    new_password: str = Field(min_length=12, max_length=1024)


class TwoFactorLoginRequest(Input):
    challenge: str = Field(min_length=20, max_length=256)
    code: str = Field(min_length=6, max_length=128)
    use_cookie: bool = False
