import unicodedata


SYSTEM_USER_CODIGO = 255
SYSTEM_USER_TIPO = "Clínica"
SYSTEM_USER_NOME = "Clínica"
SYSTEM_PRESTADOR_SOURCE_ID = 255
SYSTEM_PRESTADOR_CODIGO = "001"
SYSTEM_PRESTADOR_TIPO = "Clínica odontológica"


def _norm_text(value: str | None) -> str:
    txt = str(value or "").strip().lower()
    if not txt:
        return ""
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")
    return txt


def build_system_user_email(clinica_id: int) -> str:
    return f"clinica.{SYSTEM_USER_CODIGO}.c{int(clinica_id)}@system.brana.local"


def is_system_user(usuario) -> bool:
    if bool(getattr(usuario, "is_system_user", False)):
        return True
    codigo = int(getattr(usuario, "codigo", 0) or 0)
    tipo = _norm_text(getattr(usuario, "tipo_usuario", None))
    nome = _norm_text(getattr(usuario, "nome", None))
    return (
        codigo == SYSTEM_USER_CODIGO
        and tipo == _norm_text(SYSTEM_USER_TIPO)
        and nome == _norm_text(SYSTEM_USER_NOME)
    )


def is_system_prestador(prestador) -> bool:
    if bool(getattr(prestador, "is_system_prestador", False)):
        return True
    source_id = int(getattr(prestador, "source_id", 0) or 0)
    codigo = str(getattr(prestador, "codigo", "") or "").strip()
    nome = _norm_text(getattr(prestador, "nome", None))
    return (
        source_id == SYSTEM_PRESTADOR_SOURCE_ID
        and codigo == SYSTEM_PRESTADOR_CODIGO
        and nome == _norm_text(SYSTEM_USER_NOME)
    )
