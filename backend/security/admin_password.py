from sqlalchemy.orm import Session

from models.clinica import Clinica
from models.usuario import Usuario
from security.hash import verify_password
from security.superadmin import is_owner_email
from security.system_accounts import is_system_user


def _admin_candidates(db: Session, clinica_id: int) -> list[Usuario]:
    return (
        db.query(Usuario)
        .filter(
            Usuario.clinica_id == int(clinica_id),
            Usuario.is_admin == True,  # noqa: E712
        )
        .order_by(Usuario.id.asc())
        .all()
    )


def resolve_admin_user(db: Session, clinica_id: int) -> Usuario | None:
    admins = [u for u in _admin_candidates(db, clinica_id) if not is_system_user(u)]
    if not admins:
        return None

    clinica_email = (
        db.query(Clinica.email)
        .filter(Clinica.id == int(clinica_id))
        .scalar()
    )
    if clinica_email:
        clinica_email = str(clinica_email).strip().lower()
        for usuario in admins:
            if (usuario.email or "").strip().lower() == clinica_email:
                return usuario

    for usuario in admins:
        if is_owner_email(getattr(usuario, "email", None)):
            return usuario

    return admins[0]


def verify_admin_password(db: Session, clinica_id: int, senha: str) -> bool:
    admin = resolve_admin_user(db, clinica_id)
    if not admin:
        return False
    return verify_password((senha or "").strip(), admin.senha_hash)
