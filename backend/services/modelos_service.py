from pathlib import Path

from sqlalchemy.orm import Session

from models.modelo_documento import ModeloDocumento


PROJECT_DIR = Path(__file__).resolve().parents[3]
MODEL_STORAGE_DIR = PROJECT_DIR / "saas" / "storage" / "modelos"
MODELO_TIPOS_DIR = {
    "atestados",
    "receitas",
    "recibos",
    "etiquetas",
    "orcamentos",
    "email_agenda",
    "whatsapp_agenda",
    "outros",
}
ORIGENS_STORAGE = {
    "base": "base",
    "clinicas": "clinica",
}


def _codigo_modelo_por_arquivo(tipo_modelo: str, arquivo: Path) -> str:
    base = arquivo.stem.strip().lower().replace(" ", "_")
    base = "".join(ch for ch in base if ch.isalnum() or ch in {"_", "-"})
    return f"{tipo_modelo}:{base}"[:80]


def _nome_exibicao_por_arquivo(arquivo: Path) -> str:
    return arquivo.stem.strip() or arquivo.name


def _iter_storage_records():
    if not MODEL_STORAGE_DIR.exists():
        return
    for scope_dir in sorted(MODEL_STORAGE_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not scope_dir.is_dir() or scope_dir.name not in ORIGENS_STORAGE:
            continue
        if scope_dir.name == "base":
            for tipo_dir in sorted(scope_dir.iterdir(), key=lambda p: p.name.lower()):
                if not tipo_dir.is_dir() or tipo_dir.name not in MODELO_TIPOS_DIR:
                    continue
                for arquivo in sorted(tipo_dir.iterdir(), key=lambda p: p.name.lower()):
                    if arquivo.is_file():
                        yield {
                            "clinica_id": None,
                            "tipo_modelo": tipo_dir.name,
                            "arquivo": arquivo,
                            "origem": "base",
                        }
            continue
        for clinica_dir in sorted(scope_dir.iterdir(), key=lambda p: p.name.lower()):
            if not clinica_dir.is_dir():
                continue
            try:
                clinica_id = int(clinica_dir.name)
            except Exception:
                continue
            for tipo_dir in sorted(clinica_dir.iterdir(), key=lambda p: p.name.lower()):
                if not tipo_dir.is_dir() or tipo_dir.name not in MODELO_TIPOS_DIR:
                    continue
                for arquivo in sorted(tipo_dir.iterdir(), key=lambda p: p.name.lower()):
                    if arquivo.is_file():
                        yield {
                            "clinica_id": clinica_id,
                            "tipo_modelo": tipo_dir.name,
                            "arquivo": arquivo,
                            "origem": "clinica",
                        }


def sincronizar_catalogo_modelos_storage(db: Session) -> dict:
    vistos = set()
    inseridos = 0
    atualizados = 0

    existentes = (
        db.query(ModeloDocumento)
        .filter(ModeloDocumento.origem.in_(("base", "clinica")))
        .all()
    )
    por_chave = {
        (
            int(item.clinica_id) if item.clinica_id is not None else None,
            str(item.tipo_modelo or "").strip(),
            str(item.nome_arquivo or "").strip(),
        ): item
        for item in existentes
    }

    for item in _iter_storage_records() or []:
        arquivo = item["arquivo"]
        key = (
            item["clinica_id"],
            item["tipo_modelo"],
            arquivo.name,
        )
        vistos.add(key)
        rel_path = arquivo.resolve().relative_to(PROJECT_DIR.resolve()).as_posix()
        registro = por_chave.get(key)
        if registro is None:
            registro = ModeloDocumento(
                clinica_id=item["clinica_id"],
                tipo_modelo=item["tipo_modelo"],
                codigo=_codigo_modelo_por_arquivo(item["tipo_modelo"], arquivo),
                nome_exibicao=_nome_exibicao_por_arquivo(arquivo),
                nome_arquivo=arquivo.name,
                extensao=arquivo.suffix.lower(),
                caminho_arquivo=rel_path,
                ativo=True,
                padrao_clinica=False,
                origem=item["origem"],
            )
            db.add(registro)
            por_chave[key] = registro
            inseridos += 1
            continue

        mudou = False
        novo_codigo = _codigo_modelo_por_arquivo(item["tipo_modelo"], arquivo)
        novo_nome = _nome_exibicao_por_arquivo(arquivo)
        nova_ext = arquivo.suffix.lower()
        if registro.codigo != novo_codigo:
            registro.codigo = novo_codigo
            mudou = True
        if registro.nome_exibicao != novo_nome:
            registro.nome_exibicao = novo_nome
            mudou = True
        if registro.extensao != nova_ext:
            registro.extensao = nova_ext
            mudou = True
        if registro.caminho_arquivo != rel_path:
            registro.caminho_arquivo = rel_path
            mudou = True
        if not registro.ativo:
            registro.ativo = True
            mudou = True
        if registro.origem != item["origem"]:
            registro.origem = item["origem"]
            mudou = True
        if mudou:
            atualizados += 1

    desativados = 0
    for registro in existentes:
        key = (
            int(registro.clinica_id) if registro.clinica_id is not None else None,
            str(registro.tipo_modelo or "").strip(),
            str(registro.nome_arquivo or "").strip(),
        )
        if key not in vistos and registro.ativo:
            registro.ativo = False
            desativados += 1

    return {
        "inseridos": inseridos,
        "atualizados": atualizados,
        "desativados": desativados,
        "vistos": len(vistos),
    }
