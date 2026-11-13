"""Carga do modelo no PostgreSQL/Supabase (usada por scripts/carregar_supabase.py e pelos testes)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from .loader import padronizar_frames

ROOT = Path(__file__).resolve().parent.parent
SQL_SCHEMA = ROOT / "sql" / "01_schema.sql"

# ordem de inserção (pais antes dos filhos)
ORDEM = ["dimensao", "categoria_atividade", "comunidade", "item_doacao", "atividade", "oferta", "familia",
         "morador", "participante", "participacao", "avaliacao"]
IDENTIDADE = {"dimensao": "id_dimensao", "categoria_atividade": "id_categoria", "comunidade": "id_comunidade",
              "item_doacao": "id_item_doacao", "atividade": "id_atividade", "oferta": "id_oferta",
              "morador": "id_morador", "participante": "id_participante", "participacao": "id_participacao",
              "avaliacao": "id_avaliacao"}


def criar_esquema(engine) -> None:
    with engine.begin() as conn:
        # o driver psycopg2 trata "%" como parâmetro; o script usa format('%I') e precisa de "%%"
        conn.exec_driver_sql(SQL_SCHEMA.read_text(encoding="utf-8").replace("%", "%%"))


def _limpar(conn, reset: bool) -> None:
    if reset:  # apaga também tabelas que dependem destas (projetos, rubricas, indicadores...)
        conn.execute(text("truncate table " + ", ".join(f"core.{t}" for t in ORDEM)
                          + ", core.carga_qualidade restart identity cascade"))
        return
    for t in reversed(ORDEM):  # sem cascata: se algo depende dos dados, o banco recusa e nada é apagado
        conn.execute(text(f"delete from core.{t}"))
    conn.execute(text("delete from core.carga_qualidade"))


def carregar(engine, frames: dict[str, pd.DataFrame], qualidade: pd.DataFrame, mascarado: bool, origem: str,
             reset: bool = False) -> dict[str, int]:
    """Substitui os dados de `core` pelos do modelo, em uma única transação. Devolve linhas por tabela."""
    resumo: dict[str, int] = {}
    frames = padronizar_frames(frames)   # grava o banco já com a caixa dos textos padronizada
    with engine.begin() as conn:
        _limpar(conn, reset)
        for t in ORDEM:
            df = frames[t]
            df.to_sql(t, conn, schema="core", if_exists="append", index=False, method="multi", chunksize=500)
            resumo[t] = int(len(df))
        if len(qualidade):
            q = qualidade[["id", "problema", "ocorrencias", "base", "percentual"]].astype(object)
            q = q.where(q.notna(), None)
            q.to_sql("carga_qualidade", conn, schema="core", if_exists="append", index=False, method="multi")
        for t, col in IDENTIDADE.items():  # próximos cadastros manuais continuam a numeração
            conn.execute(text(f"select setval(pg_get_serial_sequence('core.{t}', '{col}'), "
                              f"coalesce((select max({col}) from core.{t}), 0) + 1, false)"))
        conn.execute(text(
            "insert into core.carga_info (id, carregado_em, origem, mascarado, resumo) "
            "values (1, now(), :o, :m, cast(:r as jsonb)) "
            "on conflict (id) do update set carregado_em = now(), origem = :o, mascarado = :m, resumo = cast(:r as jsonb)"),
            {"o": origem, "m": bool(mascarado), "r": json.dumps(resumo)})
    return resumo
