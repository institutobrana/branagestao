from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\x00", "").strip()
    while text and ord(text[0]) < 32:
        text = text[1:]
    return " ".join(text.split())


def _to_bool_str(value: str | None) -> str:
    base = _clean_text(value or "").lower()
    return "1" if base in {"1", "-1", "true", "t", "sim", "s", "yes", "y"} else "0"


def _read_csv(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str], delimiter: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepara CSVs de contatos, proteticos/servicos e CID a partir dos exports do EDS70."
    )
    parser.add_argument("--contato-csv", required=True)
    parser.add_argument("--tipo-contato-csv", required=True)
    parser.add_argument("--tab-prt-item-csv", required=True)
    parser.add_argument("--cid-item-csv", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--delimiter", default=";")
    args = parser.parse_args()

    contato_rows = _read_csv(Path(args.contato_csv), args.delimiter)
    tipo_rows = _read_csv(Path(args.tipo_contato_csv), args.delimiter)
    prt_rows = _read_csv(Path(args.tab_prt_item_csv), args.delimiter)
    cid_rows = _read_csv(Path(args.cid_item_csv), args.delimiter)

    tipo_map: dict[str, str] = {}
    for row in tipo_rows:
        key = _clean_text(row.get("REGISTRO"))
        nome = _clean_text(row.get("NOME"))
        if key:
            tipo_map[key] = nome

    contato_map: dict[str, str] = {}
    contatos_out: list[dict[str, str]] = []
    for row in contato_rows:
        nro = _clean_text(row.get("NROCONTATO"))
        nome = _clean_text(row.get("NOME"))
        if nro and nome:
            contato_map[nro] = nome

        tipo_raw = _clean_text(row.get("TIPO"))
        tipo = tipo_map.get(tipo_raw, tipo_raw)
        contatos_out.append(
            {
                "nome": nome,
                "tipo": tipo,
                "contato": _clean_text(row.get("CONTATO")),
                "aniversario_dia": _clean_text(row.get("DIAANI")),
                "aniversario_mes": _clean_text(row.get("MESANI")),
                "endereco": _clean_text(row.get("ENDERECO")),
                "complemento": _clean_text(row.get("COMPLEM")),
                "bairro": _clean_text(row.get("BAIRRO")),
                "cidade": _clean_text(row.get("CIDADE")),
                "cep": _clean_text(row.get("CEP")),
                "uf": _clean_text(row.get("UF")),
                "pais": _clean_text(row.get("PAIS")),
                "tel1_tipo": _clean_text(row.get("TIPFONE1")),
                "tel1": _clean_text(row.get("FONE1")),
                "tel2_tipo": _clean_text(row.get("TIPFONE2")),
                "tel2": _clean_text(row.get("FONE2")),
                "tel3_tipo": _clean_text(row.get("TIPFONE3")),
                "tel3": _clean_text(row.get("FONE3")),
                "tel4_tipo": _clean_text(row.get("TIPFONE4")),
                "tel4": _clean_text(row.get("FONE4")),
                "email": _clean_text(row.get("EMAIL")),
                "homepage": _clean_text(row.get("HOMEPAGE")),
                "incluir_malas_diretas": _to_bool_str(row.get("MALADIRETA")),
                "incluir_preferidos": _to_bool_str(row.get("PREFERIDO")),
                "observacoes": _clean_text(row.get("OBSERV")),
            }
        )

    proteticos_out: list[dict[str, str]] = []
    for row in contatos_out:
        if "prot" in (row.get("tipo") or "").lower():
            if row.get("nome"):
                proteticos_out.append({"nome": row["nome"]})

    servicos_out: list[dict[str, str]] = []
    for row in prt_rows:
        nropro = _clean_text(row.get("NROPRO"))
        prot_nome = contato_map.get(nropro, "")
        nome = _clean_text(row.get("DESCRICAO"))
        if not prot_nome or not nome:
            continue
        servicos_out.append(
            {
                "protetico_nome": prot_nome,
                "nome": nome,
                "indice": "R$",
                "preco": _clean_text(row.get("PRECO")),
                "prazo": _clean_text(row.get("PRAZO")),
            }
        )

    cid_out: list[dict[str, str]] = []
    for row in cid_rows:
        codigo = _clean_text(row.get("CODIGO"))
        descricao = _clean_text(row.get("NOME"))
        if not codigo or not descricao:
            continue
        cid_out.append(
            {
                "codigo": codigo,
                "descricao": descricao,
                "observacoes": _clean_text(row.get("OBSERV")),
                "preferido": _to_bool_str(row.get("PREFERIDO")),
            }
        )

    out_dir = Path(args.out_dir)
    _write_csv(
        out_dir / "contatos_migracao.csv",
        contatos_out,
        [
            "nome",
            "tipo",
            "contato",
            "aniversario_dia",
            "aniversario_mes",
            "endereco",
            "complemento",
            "bairro",
            "cidade",
            "cep",
            "uf",
            "pais",
            "tel1_tipo",
            "tel1",
            "tel2_tipo",
            "tel2",
            "tel3_tipo",
            "tel3",
            "tel4_tipo",
            "tel4",
            "email",
            "homepage",
            "incluir_malas_diretas",
            "incluir_preferidos",
            "observacoes",
        ],
        args.delimiter,
    )
    _write_csv(out_dir / "proteticos_migracao.csv", proteticos_out, ["nome"], args.delimiter)
    _write_csv(
        out_dir / "servicos_protetico_migracao.csv",
        servicos_out,
        ["protetico_nome", "nome", "indice", "preco", "prazo"],
        args.delimiter,
    )
    _write_csv(out_dir / "cid_migracao.csv", cid_out, ["codigo", "descricao", "observacoes", "preferido"], args.delimiter)

    print(f"Contatos preparados: {len(contatos_out)}")
    print(f"Proteticos preparados: {len(proteticos_out)}")
    print(f"Servicos de protetico preparados: {len(servicos_out)}")
    print(f"CID preparado: {len(cid_out)}")
    print(f"Saida: {out_dir}")


if __name__ == "__main__":
    main()
