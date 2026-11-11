"""Acesso ao banco (Supabase/PostgreSQL) para auditoria e feedback persistentes."""
from __future__ import annotations

import streamlit as st


def usa_banco(settings) -> bool:
    return getattr(settings, "backend", "xlsx") == "postgres" and bool(getattr(settings, "postgres_url", None))


@st.cache_resource
def engine(url: str):
    from sqlalchemy import create_engine
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2)
