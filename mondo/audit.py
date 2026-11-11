"""Registro de auditoria em CSV (logs/log_acesso.csv).

Mesmas colunas da tabela `acesso.log_acesso` da documentação, para migrar depois ao banco.
Nunca grave conteúdo de buscas nem dados pessoais no log: só ação, recurso e quantidade de linhas.
Em hospedagens com disco temporário (ex.: Streamlit Community Cloud) este arquivo se perde ao reiniciar;
na fase do banco o registro passa a ser gravado no Supabase.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import pandas as pd

from . import db

COLUNAS = ["momento", "email", "nivel", "acao", "recurso", "filtros", "linhas"]


def registrar(settings, email, nivel, acao, recurso=None, filtros=None, linhas=None) -> None:
    if db.usa_banco(settings):
        try:
            from sqlalchemy import text
            with db.engine(settings.postgres_url).begin() as conn:
                conn.execute(text("insert into acesso.log_acesso (email, nivel, acao, recurso, filtros, linhas) "
                                  "values (:e, :n, :a, :r, cast(:f as jsonb), :l)"),
                             {"e": email or None, "n": nivel, "a": acao, "r": recurso or None,
                              "f": json.dumps(filtros, ensure_ascii=False) if filtros else None,
                              "l": None if linhas is None else int(linhas)})
            return
        except Exception:
            pass  # se o banco falhar, o registro cai para o arquivo local
    caminho = settings.log_path
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        novo = not caminho.exists()
        with open(caminho, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if novo:
                w.writerow(COLUNAS)
            w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), email or "", nivel, acao,
                        recurso or "", json.dumps(filtros, ensure_ascii=False) if filtros else "",
                        "" if linhas is None else int(linhas)])
    except OSError:
        pass  # o app não deve quebrar por falha de log


def ler(settings, ultimas: int = 500) -> pd.DataFrame:
    if db.usa_banco(settings):
        try:
            from sqlalchemy import text
            with db.engine(settings.postgres_url).connect() as conn:
                df = pd.read_sql(text("select to_char(momento at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS') as momento, "
                                      "coalesce(email, '') as email, nivel, acao, coalesce(recurso, '') as recurso, "
                                      "coalesce(filtros::text, '') as filtros, coalesce(linhas::text, '') as linhas "
                                      "from acesso.log_acesso order by id_log desc limit :n"), conn, params={"n": ultimas})
            return df.astype(str)
        except Exception:
            pass
    caminho = settings.log_path
    if not caminho.exists():
        return pd.DataFrame(columns=COLUNAS)
    df = pd.read_csv(caminho, dtype=str).fillna("")
    return df.tail(ultimas).iloc[::-1].reset_index(drop=True)
