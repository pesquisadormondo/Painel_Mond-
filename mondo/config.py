"""Configurações do app (lidas de .streamlit/secrets.toml e variáveis de ambiente)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
LEVEL_PUBLIC, LEVEL_RESEARCHER, LEVEL_ADMIN = "publico", "pesquisador", "admin"
LEVEL_LABELS = {
    LEVEL_PUBLIC: "Público",
    LEVEL_RESEARCHER: "Pesquisador",
    LEVEL_ADMIN: "Administrador",
}
LEVEL_ORDER = {LEVEL_PUBLIC: 0, LEVEL_RESEARCHER: 1, LEVEL_ADMIN: 2}


def secret(path: str, default=None):
    """Lê um valor de st.secrets usando caminho com pontos (ex.: 'privacy.k_min')."""
    try:
        node = st.secrets
        for part in path.split("."):
            node = node[part]
        return node
    except Exception:
        return default


@dataclass(frozen=True)
class Settings:
    backend: str                 # "xlsx" ou "postgres"
    xlsx_path: Path | None
    postgres_url: str | None
    k_min: int                   # tamanho mínimo de célula (LGPD / supressão)
    pseudo_secret: str | None    # chave do HMAC (pseudonimização)
    dev_mode: bool               # permite escolher o nível sem login Google (NUNCA em produção)
    log_path: Path
    ref_date: date               # data de referência para calcular idades


def _find_xlsx() -> Path | None:
    configured = secret("data.xlsx_path")
    if configured:
        return Path(configured)
    candidates = sorted((ROOT / "data").glob("*.xlsx"))
    return candidates[0] if candidates else None


def get_settings() -> Settings:
    return Settings(
        backend=str(secret("data.backend", "xlsx")),
        xlsx_path=_find_xlsx(),
        postgres_url=secret("data.postgres_url"),
        k_min=int(secret("privacy.k_min", 5)),
        pseudo_secret=secret("privacy.pseudo_secret") or os.getenv("MONDO_PSEUDO_SECRET"),
        dev_mode=bool(secret("dev.enabled", False)) or os.getenv("MONDO_DEV") == "1",
        log_path=Path(secret("audit.path") or ROOT / "logs" / "log_acesso.csv"),
        ref_date=date.today(),
    )
