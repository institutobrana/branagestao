from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models.usuario import Usuario
from security.jwt_handler import decode_token
from security.superadmin import is_superadmin_account_type


def verify_trial_active(token: str, db: Session):

    payload = decode_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Sessão expirada, faça login novamente!")

    user_id = payload.get("user_id")

    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()

    if not usuario:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    clinica = usuario.clinica

    if not clinica:
        raise HTTPException(status_code=401, detail="Clínica não encontrada")

    if is_superadmin_account_type(clinica.tipo_conta):
        return usuario

    if clinica.trial_ate < datetime.utcnow():
        raise HTTPException(
            status_code=403,
            detail="Trial expirado. Entre em contato com suporte."
        )

    return usuario
