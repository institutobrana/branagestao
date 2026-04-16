import os
from dataclasses import dataclass

TRUE_VALUES = {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class RuntimePolicy:
    profile: str
    enable_schema_bootstrap: bool
    enable_runtime_bootstrap: bool
    allow_http_runtime_bootstrap: bool
    allow_schema_compat_apply: bool


def env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in TRUE_VALUES


def _profile() -> str:
    raw_value = str(os.getenv("BRANA_RUNTIME_PROFILE", "local")).strip().lower()
    return raw_value or "local"


def resolve_runtime_policy() -> RuntimePolicy:
    profile = _profile()
    default_bootstrap = profile in {"local", "dev", "development"}
    return RuntimePolicy(
        profile=profile,
        enable_schema_bootstrap=env_flag("BRANA_ENABLE_SCHEMA_BOOTSTRAP", default_bootstrap),
        enable_runtime_bootstrap=env_flag("BRANA_ENABLE_RUNTIME_BOOTSTRAP", default_bootstrap),
        allow_http_runtime_bootstrap=env_flag("BRANA_ALLOW_HTTP_RUNTIME_BOOTSTRAP", False),
        allow_schema_compat_apply=env_flag("BRANA_ALLOW_SCHEMA_COMPAT_APPLY", False),
    )
