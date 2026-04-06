from __future__ import annotations

import argparse
import json
import subprocess
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import psycopg2


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OSQL_PATH = Path(r"E:\UTIL\EasyDental_7.6_BR\EDS75_Server\x86\Binn\osql.exe")
DEFAULT_SEED_PATH = PROJECT_ROOT / "Dados" / "auxiliares_easydental_seed.json"
DEFAULT_ENV_PATH = BACKEND_DIR / ".env"

QUERY_BY_TIPO: dict[str, str] = {
    "Bairro": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _BAIRRO ORDER BY REGISTRO",
    "Bancos": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _BANCO ORDER BY REGISTRO",
    "Cidade": (
        "SELECT LTRIM(RTRIM(CODIGO)), "
        "LTRIM(RTRIM(CASE WHEN ISNULL(UF,'')<>'' THEN NOME + ' / ' + UF ELSE NOME END)) "
        "FROM _CIDADE ORDER BY REGISTRO"
    ),
    "Especialidade": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _ESPECIALIDADE ORDER BY REGISTRO",
    "Estado civil": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _ESTADO_CIVIL ORDER BY REGISTRO",
    "Fabricantes": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _FABRICANTE ORDER BY REGISTRO",
    "Fase procedimento": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _FASE_PROCEDIMENTO ORDER BY REGISTRO",
    "Índices de moeda": "SELECT LTRIM(RTRIM(CONVERT(VARCHAR(10), NROIND))), LTRIM(RTRIM(SIGLA)) FROM _INDICE ORDER BY NROIND",
    "Grupo de medicamento": (
        "SELECT RIGHT('0000' + LTRIM(RTRIM(CONVERT(VARCHAR(10), NROGRUPO))), 4), "
        "LTRIM(RTRIM(NOME)) FROM DEF_GRUPO ORDER BY NROGRUPO"
    ),
    "Motivo de atestado": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _MOTIVO_ATESTADO ORDER BY REGISTRO",
    "Motivo de retorno": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _MOTIVO_RETORNO ORDER BY REGISTRO",
    "Palavra chave": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _PALAVRA_CHAVE ORDER BY REGISTRO",
    "Prefixo pessoais": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _PREFIXO_PESSOA ORDER BY REGISTRO",
    "Situação do agendamento": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _STATUS_AGENDA ORDER BY REGISTRO",
    "Situação do paciente": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _STATUS_PACIENTE ORDER BY REGISTRO",
    "Tipos de apresentação": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _TIPO_APRESENTACAO ORDER BY REGISTRO",
    "Tipos de cobrança": (
        "SELECT LTRIM(RTRIM(CODIGO)), "
        "LTRIM(RTRIM(CASE WHEN ISNULL(DESCRICAO,'')<>'' THEN DESCRICAO ELSE NOME END)) "
        "FROM _TIPO_COBRANCA ORDER BY REGISTRO"
    ),
    "Tipos de contato": (
        "SELECT RIGHT('00' + LTRIM(RTRIM(CONVERT(VARCHAR(10), REGISTRO))), 2), "
        "LTRIM(RTRIM(NOME)) FROM _TIPO_CONTATO ORDER BY REGISTRO"
    ),
    "Tipos de indicação": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _TIPO_INDICA ORDER BY REGISTRO",
    "Tipos de logradouro": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _TIPO_LOGRADOURO ORDER BY REGISTRO",
    "Tipos de material": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _TIPO_MAT ORDER BY REGISTRO",
    "Tipos de pagamento": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _TIPO_PAGTO ORDER BY REGISTRO",
    "CBO-S": (
        "SELECT LTRIM(RTRIM(CODIGO)), "
        "LTRIM(RTRIM(CASE WHEN ISNULL(NOME,'')<>'' THEN NOME ELSE DESCRICAO END)) "
        "FROM _TISS_CBOS ORDER BY REGISTRO"
    ),
    "Tipos de prestador": (
        "SELECT RIGHT('00' + LTRIM(RTRIM(CONVERT(VARCHAR(10), REGISTRO))), 2), "
        "LTRIM(RTRIM(NOME)) FROM _TIPO_PREST ORDER BY REGISTRO"
    ),
    "Tipos de uso": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _TIPO_USO ORDER BY REGISTRO",
    "Tipos de usuário": (
        "SELECT RIGHT('00' + LTRIM(RTRIM(CONVERT(VARCHAR(10), REGISTRO))), 2), "
        "LTRIM(RTRIM(CASE WHEN ISNULL(DESCRICAO,'')<>'' THEN DESCRICAO ELSE NOME END)) "
        "FROM _TIPO_USUARIO ORDER BY REGISTRO"
    ),
    "Unidades de medida": "SELECT LTRIM(RTRIM(CODIGO)), LTRIM(RTRIM(NOME)) FROM _UNID_MEDIDA ORDER BY REGISTRO",
}

# Mapa operacional das auxiliares para reaproveitar em novas migrações de módulos.
# Ideia: ao começar um módulo novo, consultar este script primeiro para ver
# se ele depende de alguma tabela auxiliar do Easy e evitar combos hardcoded.
AUX_MODULO_DEPENDENCIAS: dict[str, list[str]] = {
    "Bairro": ["Configuração de itens", "Agenda de contatos", "Convênios e planos", "Ficha pessoal"],
    "Bancos": ["Configuração de itens", "Prestadores"],
    "Cidade": ["Configuração de itens", "Agenda de contatos", "Convênios e planos", "Ficha pessoal", "Prestadores"],
    "Especialidade": ["Configuração de itens", "Prestadores", "Procedimentos", "Repasses/Comissões"],
    "Estado civil": ["Configuração de itens", "Prestadores", "Ficha pessoal"],
    "Fabricantes": ["Configuração de itens", "Materiais"],
    "Fase procedimento": ["Configuração de itens", "Procedimentos genéricos"],
    "Grupo de medicamento": ["Configuração de itens", "Medicamentos"],
    "Motivo de atestado": ["Configuração de itens", "Paciente / clínico"],
    "Motivo de retorno": ["Configuração de itens", "Paciente", "Agenda"],
    "Palavra chave": ["Configuração de itens", "Agenda de contatos"],
    "Prefixo pessoais": ["Configuração de itens", "Prestadores", "Ficha pessoal"],
    "Situação do agendamento": ["Configuração de itens", "Agenda"],
    "Situação do paciente": ["Configuração de itens", "Ficha pessoal", "Pacientes"],
    "Tipos de apresentação": ["Configuração de itens", "Procedimentos/relatórios"],
    "Tipos de cobrança": ["Configuração de itens", "Procedimentos", "Financeiro"],
    "Tipos de contato": ["Configuração de itens", "Agenda de contatos", "Prestadores", "Ficha pessoal", "Convênios e planos"],
    "Tipos de indicação": ["Configuração de itens", "Ficha pessoal", "Pacientes"],
    "Tipos de logradouro": ["Prestadores", "Convênios e planos"],
    "Tipos de material": ["Configuração de itens", "Materiais"],
    "Tipos de pagamento": ["Configuração de itens", "Prestadores", "Financeiro", "Conta corrente"],
    "CBO-S": ["Prestadores", "TISS/credenciamentos"],
    "Tipos de prestador": ["Prestadores"],
    "Tipos de uso": ["Configuração de itens", "Materiais/estoque"],
    "Tipos de usuário": ["Configuração de itens", "Usuários"],
    "Unidades de medida": ["Configuração de itens", "Materiais"],
    "Índices de moeda": ["Financeiro", "Orçamentos/relatórios"],
}

# Checklist operacional para usar este script como ponto de partida
# quando um módulo novo ainda não foi implementado no SaaS.
MODULO_STARTER_GUIDE: dict[str, list[str]] = {
    "Prestadores": [
        "Conferir tipos de prestador, CBO-S, bancos, estado civil, prefixo, tipos de pagamento, cidade, logradouro e tipos de contato.",
        "Validar se especialidade vem da auxiliar ativa e preservar valores legados inativos ao editar.",
        "Revisar todas as combos do modal antes de mexer em CRUD, agenda, convênios e comissões.",
    ],
    "Ficha pessoal": [
        "Conferir prefixo, estado civil, situação do paciente, tipos de indicação e tipos de contato.",
        "Revisar convênio, plano e tabela em domínio próprio e manter fallback para valores antigos.",
        "Trocar bairro e cidade por auxiliares quando o Easy usar combo, preservando legado ao editar.",
    ],
    "Agenda de contatos": [
        "Conferir tipos de contato para telefones, bairro, cidade, especialidade e palavra-chave.",
        "Não confundir tipo do cadastro do contato com tipo do telefone.",
        "Preservar valores legados quando a auxiliar atual não tiver mais o item salvo no Easy.",
    ],
    "Convênios e planos": [
        "Conferir tipos de logradouro, tipos de contato, bairro e cidade no cadastro do convênio.",
        "Revisar se o Easy usa auxiliar ou texto livre em cada campo antes de trocar a tela no SaaS.",
        "Validar reflexo em ficha pessoal, tratamentos, credenciamentos e comissões.",
    ],
    "Procedimentos": [
        "Conferir especialidade, tipos de cobrança, fabricantes, tipos de material e unidades de medida.",
        "Respeitar a ordenação da auxiliar quando ela tiver campo de ordem.",
        "Separar o que é auxiliar do que é módulo próprio, como símbolo gráfico.",
    ],
    "Procedimentos genéricos": [
        "Conferir especialidade e fase do procedimento via auxiliares.",
        "Validar se os campos visuais vêm de módulo próprio ou da tabela auxiliar.",
        "Garantir reflexo consistente nos procedimentos particulares e de convênio.",
    ],
    "Materiais": [
        "Conferir tipos de material, unidades de medida, fabricantes e tipos de apresentação.",
        "Trocar listas fixas por auxiliares antes de revisar visual ou relatórios.",
        "Validar reflexo em estoque, custos e procedimentos que herdam materiais.",
    ],
    "Medicamentos": [
        "Conferir grupo de medicamento na auxiliar antes de abrir o módulo.",
        "Revisar se tipos de uso, fabricantes ou apresentações também aparecem em combos do Easy.",
        "Garantir que a auxiliar saneada seja a base dos filtros e do cadastro, sem listas fixas locais.",
    ],
    "Controle de retornos": [
        "Conferir motivo de retorno e situação do paciente/agendamento nas auxiliares.",
        "Revisar o fluxo a partir da ficha do paciente e da agenda para não duplicar regras.",
        "Validar se o módulo usa apenas auxiliar ou se depende de cadastro próprio complementar.",
    ],
}


PADRONIZACAO_TELAS_FRONTEND: list[str] = [
    "Ao alterar arquivo JS/CSS referenciado em index.html, incrementar o sufixo de versÃ£o (querystring v=...) para invalidar cache.",
    "Corrigir acentuaÃ§Ã£o/caracteres na origem da tela (renderer/base), nÃ£o apenas em remendo visual posterior.",
    "Validar o mesmo fluxo em tela nova e em ediÃ§Ã£o para evitar DOM divergente entre estados.",
    "Confirmar cabeÃ§alhos/labels/colunas no frontend final antes de concluir o ajuste.",
]


def _norm(value: str) -> str:
    base = (value or "").strip().lower()
    base = unicodedata.normalize("NFD", base)
    return "".join(ch for ch in base if unicodedata.category(ch) != "Mn")


def _clean_text(value: str) -> str:
    text = (value or "").replace("\x00", "").strip()
    while text and ord(text[0]) < 32:
        text = text[1:]
    return " ".join(text.split())


def _dedupe_pairs(pairs: list[tuple[str, str]]) -> list[list[str]]:
    seen: set[tuple[str, str]] = set()
    out: list[list[str]] = []
    for code, desc in pairs:
        c = _clean_text(code)
        d = _clean_text(desc)
        if not c or not d or d.upper() == "NULL":
            continue
        key = (_norm(c), _norm(d))
        if key in seen:
            continue
        seen.add(key)
        out.append([c, d])
    return out


def _ensure_unique_codes(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    used_codes: set[str] = set()
    used_desc: set[str] = set()

    max_numeric = 0
    for code, _ in rows:
        c = _clean_text(code)
        if c.isdigit():
            max_numeric = max(max_numeric, int(c))

    out: list[list[str]] = []
    for code, desc in rows:
        c = _clean_text(code)
        d = _clean_text(desc)
        if not c or not d:
            continue

        desc_key = _norm(d)
        if desc_key in used_desc:
            continue

        code_key = _norm(c)
        if code_key in used_codes:
            while True:
                max_numeric += 1
                novo = str(max_numeric)
                novo_key = _norm(novo)
                if novo_key not in used_codes:
                    c = novo
                    code_key = novo_key
                    break

        used_codes.add(code_key)
        used_desc.add(desc_key)
        out.append([c, d])
    return out


def _tipos_relacionados_a_modulo(modulo: str) -> dict[str, list[str]]:
    alvo = _norm(modulo)
    if not alvo:
        return {}
    relacionados: dict[str, list[str]] = {}
    for tipo, modulos in AUX_MODULO_DEPENDENCIAS.items():
        hits = [nome for nome in modulos if alvo in _norm(nome)]
        if hits:
            relacionados[tipo] = hits
    return relacionados


def _print_dependencias(modulo: str | None = None) -> None:
    if modulo:
        relacionados = _tipos_relacionados_a_modulo(modulo)
        print(f"Dependências auxiliares para módulo '{modulo}':")
        if not relacionados:
            print("  (nenhuma dependência mapeada)")
            return
        for tipo in sorted(relacionados):
            print(f"- {tipo}: {', '.join(relacionados[tipo])}")
        return

    print("Mapa de dependências das tabelas auxiliares:")
    for tipo in sorted(AUX_MODULO_DEPENDENCIAS):
        print(f"- {tipo}: {', '.join(AUX_MODULO_DEPENDENCIAS[tipo])}")


def _starter_items_for_modulo(modulo: str) -> tuple[str, list[str]] | None:
    alvo = _norm(modulo)
    if not alvo:
        return None
    for nome, itens in MODULO_STARTER_GUIDE.items():
        if alvo == _norm(nome):
            return nome, itens
    for nome, itens in MODULO_STARTER_GUIDE.items():
        if alvo in _norm(nome):
            return nome, itens
    return None


def _print_modulo_starter(modulo: str | None = None) -> None:
    if modulo:
        match = _starter_items_for_modulo(modulo)
        print(f"Checklist de arranque para módulo '{modulo}':")
        if not match:
            print("  (nenhum checklist específico mapeado)")
            return
        nome, itens = match
        print(f"- Módulo base: {nome}")
        for item in itens:
            print(f"  - {item}")
        relacionados = _tipos_relacionados_a_modulo(nome)
        if relacionados:
            print("  - Auxiliares relacionadas:")
            for tipo in sorted(relacionados):
                print(f"    - {tipo}")
        return

    print("Checklist de arranque para módulos mapeados:")
    for nome in sorted(MODULO_STARTER_GUIDE):
        print(f"- {nome}")
        for item in MODULO_STARTER_GUIDE[nome]:
            print(f"  - {item}")


def _print_padronizacao_telas_frontend() -> None:
    print("Regras canÃ´nicas de padronizaÃ§Ã£o de telas frontend:")
    for item in PADRONIZACAO_TELAS_FRONTEND:
        print(f"- {item}")


def _run_osql_query(
    osql_path: Path,
    server: str,
    user: str,
    password: str,
    database: str,
    query: str,
) -> list[list[str]]:
    cmd = [
        str(osql_path),
        "-S",
        server,
        "-U",
        user,
        "-P",
        password,
        "-d",
        database,
        "-n",
        "-h-1",
        "-s",
        "|",
        "-w",
        "32767",
        "-Q",
        f"SET NOCOUNT ON; {query}",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        stderr = proc.stderr.decode("cp850", errors="replace").strip()
        stdout = proc.stdout.decode("cp850", errors="replace").strip()
        raise RuntimeError(f"osql falhou ({proc.returncode}): {stderr or stdout}")

    text = proc.stdout.decode("cp850", errors="replace")
    pairs: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        cols = [part.strip() for part in line.split("|")]
        if len(cols) < 2:
            continue
        pairs.append((cols[0], cols[1]))
    return _ensure_unique_codes(_dedupe_pairs(pairs))


def _build_seed(
    osql_path: Path,
    server: str,
    user: str,
    password: str,
    database: str,
) -> dict[str, list[list[str]]]:
    seed: dict[str, list[list[str]]] = {}
    for tipo, query in QUERY_BY_TIPO.items():
        rows = _run_osql_query(osql_path, server, user, password, database, query)
        if rows:
            seed[tipo] = rows
    return seed


def _load_database_url(env_path: Path) -> str:
    content = env_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"DATABASE_URL não encontrado em {env_path}")


def _upsert_seed_all_clinics(
    database_url: str,
    seed: dict[str, list[list[str]]],
    strict_types: set[str] | None = None,
    only_types: set[str] | None = None,
) -> dict[int, dict[str, int]]:
    strict_types = {_norm(x) for x in (strict_types or set())}
    only_types = {_norm(x) for x in (only_types or set())}
    parsed = urlparse(database_url)
    conn = psycopg2.connect(
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
    )
    conn.autocommit = False
    summary: dict[int, dict[str, int]] = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM clinicas ORDER BY id")
            clinica_ids = [int(row[0]) for row in cur.fetchall()]

            for clinica_id in clinica_ids:
                cur.execute(
                    """
                    SELECT id, tipo, codigo, descricao
                    FROM item_auxiliar
                    WHERE clinica_id = %s
                    """,
                    (clinica_id,),
                )
                existentes = cur.fetchall()

                by_code: dict[tuple[str, str], tuple[int, str]] = {}
                by_desc: dict[tuple[str, str], int] = {}
                for row_id, tipo, codigo, descricao in existentes:
                    tipo_key = _norm(str(tipo or ""))
                    cod_key = _norm(str(codigo or ""))
                    desc_key = _norm(str(descricao or ""))
                    by_code[(tipo_key, cod_key)] = (int(row_id), str(descricao or ""))
                    if desc_key:
                        by_desc[(tipo_key, desc_key)] = int(row_id)

                inserted = 0
                updated = 0
                deleted = 0
                for tipo, itens in seed.items():
                    tipo_key = _norm(tipo)
                    if only_types and tipo_key not in only_types:
                        continue
                    kept_ids: set[int] = set()
                    for codigo, descricao in itens:
                        cod = _clean_text(codigo)
                        desc = _clean_text(descricao)
                        if not cod or not desc:
                            continue
                        code_key = (tipo_key, _norm(cod))
                        desc_key = (tipo_key, _norm(desc))

                        if code_key in by_code:
                            row_id, old_desc = by_code[code_key]
                            kept_ids.add(int(row_id))
                            if _norm(old_desc) != _norm(desc):
                                cur.execute(
                                    "UPDATE item_auxiliar SET descricao = %s WHERE id = %s",
                                    (desc, row_id),
                                )
                                updated += 1
                                by_code[code_key] = (row_id, desc)
                                by_desc[desc_key] = row_id
                            continue

                        if desc_key in by_desc:
                            kept_ids.add(int(by_desc[desc_key]))
                            continue

                        cur.execute(
                            """
                            INSERT INTO item_auxiliar (clinica_id, tipo, codigo, descricao)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id
                            """,
                            (clinica_id, tipo, cod, desc),
                        )
                        row_id = int(cur.fetchone()[0])
                        inserted += 1
                        kept_ids.add(row_id)
                        by_code[code_key] = (row_id, desc)
                        by_desc[desc_key] = row_id

                    if tipo_key in strict_types:
                        cur.execute(
                            "SELECT id FROM item_auxiliar WHERE clinica_id = %s AND tipo = %s",
                            (clinica_id, tipo),
                        )
                        existentes_tipo = [int(row[0]) for row in cur.fetchall()]
                        stale_ids = [row_id for row_id in existentes_tipo if row_id not in kept_ids]
                        if stale_ids:
                            cur.execute(
                                "DELETE FROM item_auxiliar WHERE id = ANY(%s)",
                                (stale_ids,),
                            )
                            deleted += len(stale_ids)

                summary[clinica_id] = {"inseridos": inserted, "atualizados": updated, "excluidos": deleted}

        conn.commit()
        return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza tabela auxiliar do EasyDental para o SaaS e atualiza seed local."
    )
    parser.add_argument("--server", default="DELL_SERVIDOR\\EDS70")
    parser.add_argument("--database", default="eds70")
    parser.add_argument("--user", default="sa")
    parser.add_argument("--password", default="user")
    parser.add_argument("--osql-path", default=str(DEFAULT_OSQL_PATH))
    parser.add_argument("--seed-path", default=str(DEFAULT_SEED_PATH))
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument(
        "--mostrar-dependencias",
        action="store_true",
        help="Mostra o mapa de dependências das tabelas auxiliares antes da sincronização.",
    )
    parser.add_argument(
        "--modulo",
        default="",
        help="Filtra as dependências para um módulo específico, ex.: Prestadores, Agenda, Ficha pessoal.",
    )
    parser.add_argument(
        "--continuar-sincronizacao",
        action="store_true",
        help="Mesmo após mostrar dependências, continua a execução da sincronização.",
    )
    parser.add_argument(
        "--mostrar-checklist",
        action="store_true",
        help="Mostra um checklist de arranque para módulos novos antes da sincronização.",
    )
    parser.add_argument(
        "--tipos",
        default="",
        help="Lista separada por vírgula de tipos auxiliares para sincronizar, ex.: 'Grupo de medicamento,Motivo de atestado'.",
    )
    parser.add_argument(
        "--modo-estrito",
        action="store_true",
        help="Remove itens sobrando no SaaS para os tipos selecionados, espelhando exatamente o seed do Easy.",
    )
    parser.add_argument(
        "--usar-seed-local",
        action="store_true",
        help="Usa o seed JSON local existente em vez de consultar o Easy via osql.",
    )
    args = parser.parse_args()

    if args.mostrar_dependencias or args.modulo:
        _print_dependencias(args.modulo.strip() or None)
        print("")
        if not args.continuar_sincronizacao and not args.mostrar_checklist:
            return

    if args.mostrar_checklist:
        _print_modulo_starter(args.modulo.strip() or None)
        _print_padronizacao_telas_frontend()
        print("")
        if not args.continuar_sincronizacao:
            return

    tipos_filtrados = {item.strip() for item in args.tipos.split(",") if item.strip()}
    seed_path = Path(args.seed_path)
    if args.usar_seed_local:
        if not seed_path.exists():
            raise FileNotFoundError(f"Seed local não encontrado: {seed_path}")
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
    else:
        osql_path = Path(args.osql_path)
        if not osql_path.exists():
            raise FileNotFoundError(f"osql não encontrado: {osql_path}")

        seed = _build_seed(
            osql_path=osql_path,
            server=args.server,
            user=args.user,
            password=args.password,
            database=args.database,
        )
        if not seed:
            raise RuntimeError("Não foi possível montar seed das tabelas auxiliares.")
        seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")

    if tipos_filtrados:
        tipos_norm = {_norm(item) for item in tipos_filtrados}
        seed = {tipo: itens for tipo, itens in seed.items() if _norm(tipo) in tipos_norm}
        if not seed:
            raise RuntimeError("Nenhum dos tipos informados foi encontrado no seed do Easy.")

    database_url = _load_database_url(Path(args.env_path))
    summary = _upsert_seed_all_clinics(
        database_url,
        seed,
        strict_types=tipos_filtrados if args.modo_estrito else set(),
        only_types=tipos_filtrados,
    )

    print(f"Seed gravado em: {seed_path}")
    for tipo in sorted(seed):
        print(f"{tipo}: {len(seed[tipo])}")
    for clinica_id, stats in summary.items():
        print(
            f"Clínica {clinica_id}: inseridos={stats['inseridos']}, "
            f"atualizados={stats['atualizados']}, "
            f"excluidos={stats['excluidos']}"
        )


if __name__ == "__main__":
    main()
