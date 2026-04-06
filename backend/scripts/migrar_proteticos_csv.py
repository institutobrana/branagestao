from __future__ import annotations

import argparse
import csv
from pathlib import Path

from database import SessionLocal
import models.clinica  # noqa: F401
import models.usuario  # noqa: F401
from models.protetico import Protetico, ServicoProtetico


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\x00", "").strip()
    while text and ord(text[0]) < 32:
        text = text[1:]
    return " ".join(text.split())


def _get(row: dict[str, str], key: str) -> str:
    return row.get(key, "")


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa proteticos e servicos a partir de CSV.")
    parser.add_argument("--proteticos", required=True)
    parser.add_argument("--servicos", required=False, default="")
    parser.add_argument("--clinica-id", type=int, required=True)
    parser.add_argument("--delimiter", default=";")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--criar-proteticos", action="store_true")
    args = parser.parse_args()

    prot_path = Path(args.proteticos)
    if not prot_path.exists():
        raise FileNotFoundError(prot_path)

    serv_path = Path(args.servicos) if args.servicos else None
    if serv_path and not serv_path.exists():
        raise FileNotFoundError(serv_path)

    inserted = 0
    updated = 0
    skipped = 0
    serv_inserted = 0
    serv_updated = 0
    serv_skipped = 0

    db = SessionLocal()
    nomes_processados: set[str] = set()
    existentes_map: dict[str, Protetico] = {}
    try:
        existentes = db.query(Protetico).filter(Protetico.clinica_id == args.clinica_id).all()
        for item in existentes:
            existentes_map[_norm(item.nome)] = item

        with prot_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter=args.delimiter)
            for row in reader:
                nome = _clean_text(_get(row, "nome"))
                if not nome:
                    skipped += 1
                    continue
                nome_norm = _norm(nome)
                if nome_norm in nomes_processados:
                    skipped += 1
                    continue
                existente = existentes_map.get(nome_norm)
                if existente and not args.update:
                    skipped += 1
                    continue
                if existente:
                    existente.nome = nome
                    updated += 1
                else:
                    novo = Protetico(nome=nome, clinica_id=args.clinica_id)
                    db.add(novo)
                    inserted += 1
                    existentes_map[nome_norm] = novo
                nomes_processados.add(nome_norm)

        # Garante que proteticos inseridos possam ser encontrados ao importar servicos
        db.flush()

        if serv_path:
            with serv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f, delimiter=args.delimiter)
                for row in reader:
                    nome_servico = _clean_text(_get(row, "nome"))
                    prot_nome = _clean_text(_get(row, "protetico_nome") or _get(row, "protetico"))
                    if not nome_servico or not prot_nome:
                        serv_skipped += 1
                        continue
                    prot = existentes_map.get(_norm(prot_nome))
                    if not prot:
                        prot = (
                            db.query(Protetico)
                            .filter(Protetico.clinica_id == args.clinica_id, Protetico.nome == prot_nome)
                            .first()
                        )
                    if not prot and args.criar_proteticos:
                        prot = Protetico(nome=prot_nome, clinica_id=args.clinica_id)
                        db.add(prot)
                        db.flush()
                        existentes_map[_norm(prot_nome)] = prot
                    if not prot:
                        serv_skipped += 1
                        continue

                    indice = _clean_text(_get(row, "indice") or "R$")
                    try:
                        preco = float((_get(row, "preco") or "0").replace(",", "."))
                    except Exception:
                        preco = 0.0
                    try:
                        prazo = int(_get(row, "prazo") or 0)
                    except Exception:
                        prazo = 0

                    existente = (
                        db.query(ServicoProtetico)
                        .filter(
                            ServicoProtetico.clinica_id == args.clinica_id,
                            ServicoProtetico.protetico_id == prot.id,
                            ServicoProtetico.nome == nome_servico,
                        )
                        .first()
                    )
                    if existente and not args.update:
                        serv_skipped += 1
                        continue
                    if existente:
                        existente.indice = indice
                        existente.preco = preco
                        existente.prazo = prazo
                        serv_updated += 1
                    else:
                        db.add(
                            ServicoProtetico(
                                protetico_id=prot.id,
                                clinica_id=args.clinica_id,
                                nome=nome_servico,
                                indice=indice or "R$",
                                preco=preco,
                                prazo=prazo,
                            )
                        )
                        serv_inserted += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    print(f"Proteticos inseridos: {inserted} | atualizados: {updated} | pulados: {skipped}")
    print(f"Servicos inseridos: {serv_inserted} | atualizados: {serv_updated} | pulados: {serv_skipped}")
    if args.dry_run:
        print("Dry-run: nenhuma alteração persistida.")


if __name__ == "__main__":
    main()
