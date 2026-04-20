from os import environ

from .base import *


def _prod_env_bool(name: str, default: bool = False) -> bool:
    value = environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = False

SECRET_KEY = environ.get("SECRET_KEY", SECRET_KEY)

ALLOWED_HOSTS = [
    host.strip()
    for host in environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = [
        "siloxr-dev.onrender.com",
        "siloxr.com",
        "www.siloxr.com",
    ]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        origin
        for origin in [
            _origin_from_url(FRONTEND_BASE_URL),
            "https://siloxr.com",
            "https://www.siloxr.com",
        ]
        if origin
    ]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = _prod_env_bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = _prod_env_bool("CSRF_COOKIE_SECURE", True)
SECURE_SSL_REDIRECT = _prod_env_bool("SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _prod_env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = _prod_env_bool("SECURE_HSTS_PRELOAD", True)
SECURE_REFERRER_POLICY = environ.get("SECURE_REFERRER_POLICY", "same-origin")

USE_X_FORWARDED_HOST = _prod_env_bool("USE_X_FORWARDED_HOST", True)
