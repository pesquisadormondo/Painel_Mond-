"""Carrega a planilha no Supabase/PostgreSQL (schema `core`).

Exemplos:
  # ambiente de TESTE (identificações fictícias; permite administrador por senha da equipe)
  python scripts/carregar_supabase.py --url "$DATABASE_URL" --criar-esquema --mascarar

  # dados REAIS (exige confirmação digitada)
  python scripts/carregar_supabase.py --url "$DATABASE_URL" --criar-esquema

A URL pode vir da variável de ambiente DATABASE_URL. Formato: postgresql+psycopg2://usuario:senha@host:5432/postgres
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from mondo import carga, loader, mascaramento  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xlsx", help="planilha (padrão: primeiro .xlsx de data/)")
    ap.add_argument("--url", default=os.getenv("DATABASE_URL"), help="URL de conexão (ou variável DATABASE_URL)")
    ap.add_argument("--criar-esquema", action="store_true", help="executa sql/01_schema.sql antes da carga")
    ap.add_argument("--mascarar", action="store_true", help="troca identificações por dados fictícios (ambiente de teste)")
    ap.add_argument("--semente", default="mondo-teste", help="semente do mascaramento (mesma semente = mesmos nomes fictícios)")
    ap.add_argument("--reset", action="store_true", help="apaga também tabelas que dependem das dimensões (projetos, indicadores...)")
    ap.add_argument("--sim", action="store_true", help="não pedir confirmação (somente com --mascarar)")
    a = ap.parse_args()

    if not a.url:
        ap.error("informe --url ou defina DATABASE_URL")
    xlsx = Path(a.xlsx) if a.xlsx else next((p for p in sorted((ROOT / "data").glob("*.xlsx"))
                                            if not p.name.startswith((".", "~$"))), None)
    if not xlsx or not xlsx.exists():
        ap.error("planilha não encontrada: coloque um .xlsx em data/ ou use --xlsx")

    host = a.url.split("@")[-1].split("/")[0]
    print(f"Planilha : {xlsx.name}\nBanco    : {host}\nModo     : "
          + ("TESTE (dados mascarados)" if a.mascarar else "DADOS REAIS (com identificação)"))
    if not a.mascarar:
        print("\nATENÇÃO: nomes, CPF, telefones, endereços e coordenadas de famílias (inclusive crianças) serão gravados "
              "no banco.\nConfirme antes: região do projeto Supabase, base legal e quem terá acesso (LGPD).")
        if input('Para continuar digite exatamente "CARREGAR DADOS REAIS": ').strip() != "CARREGAR DADOS REAIS":
            print("Cancelado.")
            return 1
    elif not a.sim and input("Isto SUBSTITUI os dados do banco. Continuar? [s/N] ").strip().lower() != "s":
        print("Cancelado.")
        return 1

    print("Lendo e organizando a planilha…")
    frames, quali = loader.construir_modelo(loader.ler_planilha(xlsx))
    if a.mascarar:
        print("Mascarando identificações…")
        frames = mascaramento.mascarar(frames, a.semente)

    eng = create_engine(a.url, pool_pre_ping=True)
    try:
        if a.criar_esquema:
            print("Criando schemas e tabelas…")
            carga.criar_esquema(eng)
        print("Carregando…")
        resumo = carga.carregar(eng, frames, quali, mascarado=a.mascarar, origem=xlsx.name, reset=a.reset)
        with eng.connect() as conn:
            marcado = conn.execute(text("select mascarado from core.carga_info where id = 1")).scalar()
    finally:
        eng.dispose()
    print(pd.Series(resumo, name="linhas").to_string())
    print(f"\nPronto. Carga marcada como {'TESTE (mascarada)' if marcado else 'DADOS REAIS'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
