import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import func

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import Base, SessionLocal, engine
from models.clinica import Clinica
from models.convenio_odonto import ConvenioOdonto, PlanoOdonto
from models.usuario import Usuario

TARGET_EMAIL_DEFAULT = "gleissontel@gmail.com"
SOURCE_SERVER = r"DELL_SERVIDOR\EDS70"
SOURCE_DATABASE = "eds70"
SOURCE_UID = "easy"
SOURCE_PWD = "ysae"
OSQL_PATH = Path(r"D:\UTIL\EasyDental_7.6_BR\EDS75_Server\x86\Binn\OSQL.EXE")
DELIM = "|~|"


def _run_osql_query(query: str) -> list[str]:
    if not OSQL_PATH.exists():
        raise RuntimeError(f"OSQL.EXE nao encontrado em: {OSQL_PATH}")
    sql_file = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sql", encoding="latin-1") as handle:
            sql_file = handle.name
            handle.write(f"SET NOCOUNT ON\n{query}\n")
        cmd = [
            str(OSQL_PATH),
            "-S",
            SOURCE_SERVER,
            "-d",
            SOURCE_DATABASE,
            "-U",
            SOURCE_UID,
            "-P",
            SOURCE_PWD,
            "-h-1",
            "-w",
            "999",
            "-i",
            str(sql_file),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, encoding="latin-1", errors="ignore", check=True)
    finally:
        if sql_file:
            try:
                Path(sql_file).unlink(missing_ok=True)
            except OSError:
                pass
    linhas: list[str] = []
    for raw in completed.stdout.splitlines():
        line = raw.rstrip()
        if not line.strip() or DELIM not in line:
            continue
        linhas.append(line.strip())
    return linhas


def _text(value: str | None) -> str | None:
    txt = " ".join(str(value or "").replace("\ufeff", "").split()).strip()
    return txt or None


def _normalizar_nome_convenio(nome: str | None) -> str | None:
    txt = _text(nome)
    if not txt:
        return txt
    lower = txt.lower()
    if lower in {"telebr s", "telebras"}:
        return "Telebrás"
    if lower in {"petrobr s", "petrobras"}:
        return "Petrobrás"
    return txt


def _int(value: str | int | None, default: int = 0) -> int:
    txt = str(value or "").strip()
    if not txt:
        return default
    try:
        return int(float(txt.replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _bool(value: str | int | None) -> bool:
    return str(value or "0").strip() not in {"", "0", "false", "False", "F", "f"}


def _carregar_convenios_origem() -> list[dict]:
    rows = _run_osql_query(
        "SELECT "
        "CAST(NROCONV AS VARCHAR(20)) + '{d}' + "
        "ISNULL(CODIGO,'') + '{d}' + "
        "ISNULL(CODANS,'') + '{d}' + "
        "ISNULL(REPLACE(REPLACE(NOME, CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "ISNULL(REPLACE(REPLACE(RAZAO, CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "CAST(ISNULL(TIPOLOG,0) AS VARCHAR(20)) + '{d}' + "
        "ISNULL(ENDERECO,'') + '{d}' + "
        "ISNULL(NUMERO,'') + '{d}' + "
        "ISNULL(COMPLEM,'') + '{d}' + "
        "ISNULL(BAIRRO,'') + '{d}' + "
        "ISNULL(CEP,'') + '{d}' + "
        "ISNULL(CNPJ,'') + '{d}' + "
        "ISNULL(CIDADE,'') + '{d}' + "
        "ISNULL(UF,'') + '{d}' + "
        "CAST(ISNULL(TIPFONE1,0) AS VARCHAR(20)) + '{d}' + "
        "ISNULL(FONE1,'') + '{d}' + "
        "ISNULL(CONTATO1,'') + '{d}' + "
        "CAST(ISNULL(TIPFONE2,0) AS VARCHAR(20)) + '{d}' + "
        "ISNULL(FONE2,'') + '{d}' + "
        "ISNULL(CONTATO2,'') + '{d}' + "
        "CAST(ISNULL(TIPFONE3,0) AS VARCHAR(20)) + '{d}' + "
        "ISNULL(FONE3,'') + '{d}' + "
        "ISNULL(CONTATO3,'') + '{d}' + "
        "CAST(ISNULL(TIPFONE4,0) AS VARCHAR(20)) + '{d}' + "
        "ISNULL(FONE4,'') + '{d}' + "
        "ISNULL(CONTATO4,'') + '{d}' + "
        "ISNULL(EMAIL_CONTATO,'') + '{d}' + "
        "ISNULL(EMAIL_TECNICO,'') + '{d}' + "
        "ISNULL(HOMEPAGE,'') + '{d}' + "
        "ISNULL(INSC_EST,'') + '{d}' + "
        "ISNULL(INSC_MUN,'') + '{d}' + "
        "CAST(ISNULL(TIPO_FAT,0) AS VARCHAR(20)) + '{d}' + "
        "CAST(ISNULL(INATIVO,0) AS VARCHAR(10)) + '{d}' + "
        "ISNULL(REPLACE(REPLACE(CAST(HISTNF AS VARCHAR(4000)), CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "ISNULL(REPLACE(REPLACE(CAST(AVISO_TRA AS VARCHAR(4000)), CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "ISNULL(REPLACE(REPLACE(CAST(AVISO_AGE AS VARCHAR(4000)), CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "ISNULL(REPLACE(REPLACE(CAST(OBSERV AS VARCHAR(4000)), CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "ISNULL(CONVERT(VARCHAR(10), TIME_STAMP_INS, 103),'') + '{d}' + "
        "ISNULL(CONVERT(VARCHAR(10), TIME_STAMP_UPD, 103),'') "
        "FROM CONVENIO ORDER BY NROCONV".format(d=DELIM)
    )
    out: list[dict] = []
    for row in rows:
        parts = [p.strip() for p in row.split(DELIM)]
        if len(parts) != 39:
            continue
        source_id = _int(parts[0], 0)
        if source_id <= 0:
            continue
        out.append(
            {
                "source_id": source_id,
                "codigo": _text(parts[1]),
                "codigo_ans": _text(parts[2]),
                "nome": _normalizar_nome_convenio(parts[3]) or f"Convenio {source_id}",
                "razao_social": _text(parts[4]),
                "tipo_logradouro": _int(parts[5], 0) or None,
                "endereco": _text(parts[6]),
                "numero": _text(parts[7]),
                "complemento": _text(parts[8]),
                "bairro": _text(parts[9]),
                "cep": _text(parts[10]),
                "cnpj": _text(parts[11]),
                "cidade": _text(parts[12]),
                "uf": _text(parts[13]),
                "tipo_fone1": _int(parts[14], 0) or None,
                "telefone": _text(parts[15]),
                "contato1": _text(parts[16]),
                "tipo_fone2": _int(parts[17], 0) or None,
                "telefone2": _text(parts[18]),
                "contato2": _text(parts[19]),
                "tipo_fone3": _int(parts[20], 0) or None,
                "telefone3": _text(parts[21]),
                "contato3": _text(parts[22]),
                "tipo_fone4": _int(parts[23], 0) or None,
                "telefone4": _text(parts[24]),
                "contato4": _text(parts[25]),
                "email": _text(parts[26]),
                "email_tecnico": _text(parts[27]),
                "homepage": _text(parts[28]),
                "inscricao_estadual": _text(parts[29]),
                "inscricao_municipal": _text(parts[30]),
                "tipo_faturamento": _int(parts[31], 0) or None,
                "inativo": _bool(parts[32]),
                "historico_nf": _text(parts[33]),
                "aviso_tratamento": _text(parts[34]),
                "aviso_agenda": _text(parts[35]),
                "observacoes": _text(parts[36]),
                "data_inclusao": _text(parts[37]),
                "data_alteracao": _text(parts[38]),
            }
        )
    return out


def _carregar_planos_origem() -> list[dict]:
    rows = _run_osql_query(
        "SELECT "
        "CAST(NROPLAN AS VARCHAR(20)) + '{d}' + "
        "ISNULL(CODPLAN,'') + '{d}' + "
        "CAST(ISNULL(NROCONV,0) AS VARCHAR(20)) + '{d}' + "
        "ISNULL(REPLACE(REPLACE(NOME, CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "CAST(ISNULL(INATIVO,0) AS VARCHAR(10)) + '{d}' + "
        "ISNULL(REPLACE(REPLACE(CAST(COBERTURA AS VARCHAR(4000)), CHAR(13), ' '), CHAR(10), ' '), '') + '{d}' + "
        "ISNULL(CONVERT(VARCHAR(10), TIME_STAMP_INS, 103),'') + '{d}' + "
        "ISNULL(CONVERT(VARCHAR(10), TIME_STAMP_UPD, 103),'') "
        "FROM PLANO ORDER BY NROPLAN".format(d=DELIM)
    )
    out: list[dict] = []
    for row in rows:
        parts = [p.strip() for p in row.split(DELIM)]
        if len(parts) != 8:
            continue
        source_id = _int(parts[0], 0)
        if source_id <= 0:
            continue
        convenio_source_id = _int(parts[2], 0) or None
        out.append(
            {
                "source_id": source_id,
                "codigo": _text(parts[1]),
                "convenio_source_id": convenio_source_id,
                "nome": _text(parts[3]) or f"Plano {source_id}",
                "inativo": _bool(parts[4]),
                "cobertura": _text(parts[5]),
                "data_inclusao": _text(parts[6]),
                "data_alteracao": _text(parts[7]),
            }
        )
    return out


def migrar(target_email: str, apply_changes: bool) -> None:
    Base.metadata.create_all(bind=engine)
    convenios_src = _carregar_convenios_origem()
    planos_src = _carregar_planos_origem()

    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(func.lower(Usuario.email) == target_email.lower()).first()
        if not usuario:
            raise RuntimeError(f"Usuario alvo nao encontrado: {target_email}")
        clinica = db.query(Clinica).filter(Clinica.id == usuario.clinica_id).first()
        if not clinica:
            raise RuntimeError("Clinica do usuario alvo nao encontrada.")

        existentes_conv = {
            int(item.source_id): item
            for item in db.query(ConvenioOdonto).filter(ConvenioOdonto.clinica_id == clinica.id).all()
        }
        existentes_plan = {
            int(item.source_id): item
            for item in db.query(PlanoOdonto).filter(PlanoOdonto.clinica_id == clinica.id).all()
        }

        print(f"Clinica alvo: id={clinica.id} usuario={target_email}")
        print(f"Convenios origem={len(convenios_src)} existentes={len(existentes_conv)}")
        print(f"Planos origem={len(planos_src)} existentes={len(existentes_plan)}")

        if not apply_changes:
            db.rollback()
            print("Dry-run concluido. Nenhuma alteracao foi gravada.")
            return

        for row in convenios_src:
            item = existentes_conv.get(int(row["source_id"]))
            if not item:
                item = ConvenioOdonto(clinica_id=clinica.id, source_id=int(row["source_id"]))
                db.add(item)
            item.codigo = row["codigo"]
            item.codigo_ans = row["codigo_ans"]
            item.nome = str(row["nome"])
            item.razao_social = row["razao_social"]
            item.tipo_logradouro = row["tipo_logradouro"]
            item.endereco = row["endereco"]
            item.numero = row["numero"]
            item.complemento = row["complemento"]
            item.bairro = row["bairro"]
            item.cep = row["cep"]
            item.cnpj = row["cnpj"]
            item.cidade = row["cidade"]
            item.uf = row["uf"]
            item.tipo_fone1 = row["tipo_fone1"]
            item.telefone = row["telefone"]
            item.contato1 = row["contato1"]
            item.tipo_fone2 = row["tipo_fone2"]
            item.telefone2 = row["telefone2"]
            item.contato2 = row["contato2"]
            item.tipo_fone3 = row["tipo_fone3"]
            item.telefone3 = row["telefone3"]
            item.contato3 = row["contato3"]
            item.tipo_fone4 = row["tipo_fone4"]
            item.telefone4 = row["telefone4"]
            item.contato4 = row["contato4"]
            item.email = row["email"]
            item.email_tecnico = row["email_tecnico"]
            item.homepage = row["homepage"]
            item.inscricao_estadual = row["inscricao_estadual"]
            item.inscricao_municipal = row["inscricao_municipal"]
            item.tipo_faturamento = row["tipo_faturamento"]
            item.historico_nf = row["historico_nf"]
            item.aviso_tratamento = row["aviso_tratamento"]
            item.aviso_agenda = row["aviso_agenda"]
            item.observacoes = row["observacoes"]
            item.inativo = bool(row["inativo"])
            item.data_inclusao = row["data_inclusao"]
            item.data_alteracao = row["data_alteracao"]
        db.flush()

        convenios_map = {
            int(item.source_id): item
            for item in db.query(ConvenioOdonto).filter(ConvenioOdonto.clinica_id == clinica.id).all()
        }

        for row in planos_src:
            item = existentes_plan.get(int(row["source_id"]))
            if not item:
                item = PlanoOdonto(clinica_id=clinica.id, source_id=int(row["source_id"]))
                db.add(item)
            item.codigo = row["codigo"]
            item.nome = str(row["nome"])
            item.convenio_source_id = row["convenio_source_id"]
            item.convenio_id = convenios_map.get(int(row["convenio_source_id"] or 0)).id if row["convenio_source_id"] and convenios_map.get(int(row["convenio_source_id"] or 0)) else None
            item.cobertura = row["cobertura"]
            item.inativo = bool(row["inativo"])
            item.data_inclusao = row["data_inclusao"]
            item.data_alteracao = row["data_alteracao"]

        db.commit()
        total_conv = db.query(ConvenioOdonto).filter(ConvenioOdonto.clinica_id == clinica.id).count()
        total_plan = db.query(PlanoOdonto).filter(PlanoOdonto.clinica_id == clinica.id).count()
        print(f"Migracao aplicada com sucesso. convenios={total_conv} planos={total_plan}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Migra Convenios e Planos do EasyDental para uma clinica do SaaS.")
    parser.add_argument("--email", default=TARGET_EMAIL_DEFAULT, help="Email do usuario alvo.")
    parser.add_argument("--apply", action="store_true", help="Aplica a migracao. Sem isso, executa apenas dry-run.")
    args = parser.parse_args()
    migrar(args.email, bool(args.apply))


if __name__ == "__main__":
    main()
