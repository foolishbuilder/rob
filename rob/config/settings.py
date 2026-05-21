from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class BaseSettings:
    app_env: str
    log_level: str
    database_url: str


@dataclass(frozen=True)
class WebhookSettings(BaseSettings):
    throne_webhook_host: str
    throne_parse_test_sends_as_real_sends: bool
    throne_test_gifter_usernames: tuple[str, ...]
    throne_webhook_port: int
    throne_webhook_base_url: str
    throne_webhook_require_signature: bool
    throne_public_key_pem: str | None
    throne_webhook_debug_log_payload: bool
    throne_webhook_timestamp_header: str
    throne_webhook_signature_header: str
    throne_webhook_signed_message_format: str
    throne_webhook_max_timestamp_skew_seconds: int


@dataclass(frozen=True)
class BotSettings(BaseSettings):
    discord_token: str
    bot_name: str


def _load_env_file(env_file: str | Path | None) -> None:
    if env_file is not None:
        load_dotenv(env_file)
        return
    load_dotenv()


def _env_str(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        if required:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return "" if default is None else default
    return value.strip()


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc

    if minimum is not None and value < minimum:
        raise RuntimeError(f"Environment variable {name} must be at least {minimum}.")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise RuntimeError(f"Environment variable {name} must be a boolean value.")


def load_base_settings(env_file: str | Path | None = None) -> BaseSettings:
    _load_env_file(env_file)
    return BaseSettings(
        app_env=_env_str("APP_ENV", "dev"),
        log_level=_env_str("LOG_LEVEL", "INFO"),
        database_url=_env_str("DATABASE_URL", required=True),
    )


def load_webhook_settings(env_file: str | Path | None = None) -> WebhookSettings:
    base = load_base_settings(env_file)
    return WebhookSettings(
        app_env=base.app_env,
        log_level=base.log_level,
        database_url=base.database_url,
        throne_webhook_host=_env_str("THRONE_WEBHOOK_HOST", "127.0.0.1"),
        throne_parse_test_sends_as_real_sends=_env_bool("THRONE_PARSE_TEST_SENDS_AS_REAL_SENDS", False),
        throne_test_gifter_usernames=tuple(u.strip().lower() for u in _env_str("THRONE_TEST_GIFTER_USERNAMES", "marie_123").split(",") if u.strip()),
        throne_webhook_port=_env_int("THRONE_WEBHOOK_PORT", 8080, minimum=1),
        throne_webhook_base_url=_env_str(
            "THRONE_WEBHOOK_BASE_URL",
            "https://rob-dev.barecoding.com",
        ),
        throne_webhook_require_signature=_env_bool(
            "THRONE_WEBHOOK_REQUIRE_SIGNATURE",
            True,
        ),
        throne_public_key_pem=_env_str("THRONE_PUBLIC_KEY_PEM") or None,
        throne_webhook_debug_log_payload=_env_bool(
            "THRONE_WEBHOOK_DEBUG_LOG_PAYLOAD",
            False,
        ),
        throne_webhook_timestamp_header=_env_str(
            "THRONE_WEBHOOK_TIMESTAMP_HEADER",
            "X-Signature-Timestamp",
        ),
        throne_webhook_signature_header=_env_str(
            "THRONE_WEBHOOK_SIGNATURE_HEADER",
            "X-Signature-Ed25519",
        ),
        throne_webhook_signed_message_format=_env_str(
            "THRONE_WEBHOOK_SIGNED_MESSAGE_FORMAT",
            "timestamp_dot_body",
        ),
        throne_webhook_max_timestamp_skew_seconds=_env_int(
            "THRONE_WEBHOOK_MAX_TIMESTAMP_SKEW_SECONDS",
            300,
            minimum=0,
        ),
    )


def load_bot_settings(env_file: str | Path | None = None) -> BotSettings:
    base = load_base_settings(env_file)
    return BotSettings(
        app_env=base.app_env,
        log_level=base.log_level,
        database_url=base.database_url,
        discord_token=_env_str("DISCORD_TOKEN", required=True),
        bot_name=_env_str("BOT_NAME", "Rob"),
    )


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
