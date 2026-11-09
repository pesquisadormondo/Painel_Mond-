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

COLUNAS = ["momento", "email", "nivel", "acao", "recurso", "filtros", "linhas"]


def registrar(settings, email, nivel, acao, recurso=None, filtros=None, linhas=None) -> None:
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
    caminho = settings.log_path
    if not caminho.exists():
        return pd.DataFrame(columns=COLUNAS)
    df = pd.read_csv(caminho, dtype=str).fillna("")
    return df.tail(ultimas).iloc[::-1].reset_index(drop=True)
