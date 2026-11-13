"""Caixa de feedback dentro do painel: grava em logs/feedback.csv (local, nada vai a serviços externos)."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from . import db

COLUNAS = ["momento", "nome", "tipo", "pagina", "texto", "filtros"]
TIPOS = ["Sugestão", "Erro ou número estranho", "Dúvida", "Elogio"]


def caminho(settings) -> Path:
    return Path(settings.log_path).parent / "feedback.csv"


def registrar(settings, nome: str, tipo: str, pagina: str, texto: str, filtros=None) -> None:
    if db.usa_banco(settings):
        try:
            from sqlalchemy import text as sql
            with db.engine(settings.postgres_url).begin() as conn:
                conn.execute(sql("insert into acesso.feedback (nome, tipo, pagina, texto, filtros) "
                                 "values (:n, :t, :p, :x, cast(:f as jsonb))"),
                             {"n": nome.strip() or None, "t": tipo, "p": pagina, "x": texto.strip(),
                              "f": json.dumps(filtros, ensure_ascii=False) if filtros else None})
            return
        except Exception:
            pass  # cai para o arquivo local
    destino = caminho(settings)
    destino.parent.mkdir(parents=True, exist_ok=True)
    novo = not destino.exists()
    with open(destino, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if novo:
            w.writerow(COLUNAS)
        w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), nome.strip(), tipo, pagina,
                    texto.strip(), json.dumps(filtros, ensure_ascii=False) if filtros else ""])


def ler(settings) -> pd.DataFrame:
    if db.usa_banco(settings):
        try:
            from sqlalchemy import text as sql
            with db.engine(settings.postgres_url).connect() as conn:
                df = pd.read_sql(sql("select to_char(momento at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS') as momento, "
                                     "coalesce(nome, '') as nome, coalesce(tipo, '') as tipo, coalesce(pagina, '') as pagina, "
                                     "texto, coalesce(filtros::text, '') as filtros from acesso.feedback "
                                     "order by id_feedback desc"), conn)
            return df.astype(str)
        except Exception:
            pass
    destino = caminho(settings)
    if not destino.exists():
        return pd.DataFrame(columns=COLUNAS)
    return pd.read_csv(destino, dtype=str).fillna("").iloc[::-1].reset_index(drop=True)


def caixa(settings, pagina: str, filtros=None) -> None:
    """Formulário na barra lateral. `pagina` é o título da tela em que a pessoa está."""
    with st.sidebar.container(key="caixa_feedback"):
        with st.expander("Enviar feedback"):
            with st.form("form_feedback", clear_on_submit=True):
                nome = st.text_input("Seu nome (opcional)")
                tipo = st.selectbox("Tipo", TIPOS)
                texto = st.text_area("O que você achou?", max_chars=1500,
                                     help="Não escreva nomes de pessoas atendidas nem CPF.")
                enviado = st.form_submit_button("Enviar")
            if enviado:
                if texto.strip():
                    registrar(settings, nome, tipo, pagina, texto, {k: v for k, v in (filtros or {}).items() if v})
                    st.success("Obrigado! Seu feedback foi registrado.")
                else:
                    st.warning("Escreva uma mensagem antes de enviar.")
