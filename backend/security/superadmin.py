import os


def _owner_emails() -> set[str]:
    raw = (
        os.getenv("OWNER_BYPASS_EMAILS", "").strip()
        or os.getenv("OWNER_MASTER_EMAIL", "").strip()
        or "gleissontel@gmail.com"
    )
    parts = [x.strip().lower() for x in raw.replace(";", ",").split(",")]
    return {x for x in parts if x}


def is_owner_email(email: str | None) -> bool:
    return (email or "").strip().lower() in _owner_emails()


def is_superadmin_account_type(tipo_conta: str | None) -> bool:
    value = " ".join((tipo_conta or "").strip().lower().split())
    return value in {"super admin", "superadmin", "master", "owner", "vitalicia", "vitalícia"}


def is_platform_superadmin_user(usuario) -> bool:
    if not usuario:
        return False
    if is_owner_email(getattr(usuario, "email", None)):
        return True
    clinica = getattr(usuario, "clinica", None)
    return bool(getattr(usuario, "is_admin", False) and clinica and is_superadmin_account_type(getattr(clinica, "tipo_conta", None)))
