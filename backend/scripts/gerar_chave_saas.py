import argparse
import base64
import hashlib
import os
from datetime import datetime, timedelta


def assinar(payload: str, secret: str) -> str:
    return hashlib.sha256(f"{payload}{secret}".encode("utf-8")).hexdigest()


def normalizar_plano(plano: str) -> str:
    valor = (plano or "").strip().upper()
    if valor in {"DEMO", "MENSAL", "ANUAL"}:
        return valor
    raise ValueError("Plano invalido. Use: DEMO, MENSAL ou ANUAL.")


def data_expiracao(plano: str, dias: int | None, exp: str | None) -> str:
    if exp:
        datetime.strptime(exp, "%Y-%m-%d")
        return exp
    qtd = dias if dias is not None else (7 if plano == "DEMO" else 30 if plano == "MENSAL" else 365)
    return (datetime.utcnow().date() + timedelta(days=qtd)).strftime("%Y-%m-%d")


def gerar_chave(clinica_id: int, plano: str, usuario: str, data_exp: str, secret: str) -> str:
    payload = f"BRANA-SAAS|{clinica_id}|{plano}|{usuario}|{data_exp}"
    assinatura = assinar(payload, secret)
    raw = f"{payload}|{assinatura}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Gerador legado de chave de licenca SaaS (apenas DEMO/MENSAL/ANUAL).")
    parser.add_argument("--clinica", type=int, required=True, help="ID da clinica (tenant).")
    parser.add_argument("--plano", type=str, required=True, help="DEMO, MENSAL ou ANUAL.")
    parser.add_argument("--usuario", type=str, required=True, help="Nome de registro.")
    parser.add_argument("--dias", type=int, default=None, help="Dias de validade (opcional).")
    parser.add_argument("--exp", type=str, default=None, help="Data de expiracao YYYY-MM-DD (ignora --dias).")
    args = parser.parse_args()

    secret = os.getenv("LICENSE_SECRET", "BRANA_PRECIFICACAO_2026")
    plano = normalizar_plano(args.plano)
    data_exp = data_expiracao(plano, args.dias, args.exp)
    chave = gerar_chave(args.clinica, plano, args.usuario.strip(), data_exp, secret)

    print("=== CHAVE SAAS ===")
    print(chave)
    print("")
    print(f"Clinica ID : {args.clinica}")
    print(f"Plano      : {plano}")
    print(f"Usuario    : {args.usuario.strip()}")
    print(f"Expiracao  : {data_exp}")


if __name__ == "__main__":
    main()
