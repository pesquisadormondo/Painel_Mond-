"""Níveis de acesso.

Nível 1 (público): sem login.
Nível 2 (pesquisador): login Google + e-mail na lista `access.researchers` (com validade opcional).
Nível 3 (administrador): login Google + e-mail na lista `access.admins`.

O login usa o recurso nativo do Streamlit (OpenID Connect com Google; seção [auth] do secrets.toml).
A autorização NÃO vem do Google: vem das listas abaixo (na fase do banco: tabela `acesso.acesso_pesquisador`).
Modo de desenvolvimento (dev.enabled = true): escolhe o nível sem login. Nunca ligue em produção.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import streamlit as st

from .config import (LEVEL_ADMIN, LEVEL_LABELS, LEVEL_ORDER, LEVEL_PUBLIC, LEVEL_RESEARCHER, secret)


@dataclass(frozen=True)
class Acesso:
    email: str | None
    nivel_real: str       # o que a conta tem direito de ver
    nivel: str            # o que está sendo exibido agora (admin pode "ver como" um nível menor)
    logado: bool
    aviso: str | None = None


def _admins() -> set[str]:
    return {str(e).strip().lower() for e in (secret("access.admins", []) or [])}


def _pesquisadores() -> dict[str, str]:
    bruto = secret("access.researchers", {}) or {}
    if isinstance(bruto, (list, tuple)):
        return {str(e).strip().lower(): "" for e in bruto}
    return {str(k).strip().lower(): str(v or "").strip() for k, v in dict(bruto).items()}


def _vigente(validade: str, hoje: date) -> bool:
    if not validade:
        return True
    try:
        return date.fromisoformat(validade) >= hoje
    except ValueError:
        return False  # validade ilegível = sem acesso (falha segura)


def nivel_do_email(email: str, hoje: date | None = None) -> tuple[str, str | None]:
    """Devolve (nível, aviso) para um e-mail já autenticado."""
    hoje = hoje or date.today()
    email = email.strip().lower()
    if email in _admins():
        return LEVEL_ADMIN, None
    pesq = _pesquisadores()
    if email in pesq:
        if _vigente(pesq[email], hoje):
            return LEVEL_RESEARCHER, None
        return LEVEL_PUBLIC, "Sua autorização de pesquisador expirou. Solicite renovação ao administrador."
    return LEVEL_PUBLIC, ("Esta conta não tem autorização para as áreas restritas. "
                          "Solicite acesso ao administrador do banco.")


def _escolher_nivel_exibido(real: str) -> str:
    opcoes = [n for n, o in LEVEL_ORDER.items() if o <= LEVEL_ORDER[real]]
    if len(opcoes) == 1:
        return real
    return st.sidebar.radio("Ver painéis como", opcoes, index=len(opcoes) - 1,
                            format_func=LEVEL_LABELS.get, key="ver_como",
                            help="Útil para conferir o que cada nível enxerga.")


def resolver_acesso(settings) -> Acesso:
    if settings.dev_mode:
        st.sidebar.warning("Modo de desenvolvimento: login desativado.")
        nivel = st.sidebar.radio("Nível (dev)", list(LEVEL_LABELS), format_func=LEVEL_LABELS.get, key="dev_nivel")
        return Acesso("dev@local", nivel, nivel, nivel != LEVEL_PUBLIC)

    usuario = st.user
    logado = bool(getattr(usuario, "is_logged_in", False))
    if not logado:
        if st.sidebar.button("Entrar com Google", key="btn_login", type="primary"):
            try:
                st.login()
            except Exception:
                st.sidebar.error("Login Google não configurado. Veja a seção 'Login com Google' do README.")
        st.sidebar.caption("Sem login você vê apenas o painel público.")
        return Acesso(None, LEVEL_PUBLIC, LEVEL_PUBLIC, False)

    email = str(usuario.get("email") or "").lower()
    if not usuario.get("email_verified", True):
        st.sidebar.error("O e-mail da conta Google não está verificado.")
        st.sidebar.button("Sair", on_click=st.logout, key="btn_logout")
        return Acesso(email, LEVEL_PUBLIC, LEVEL_PUBLIC, True, "E-mail não verificado.")

    real, aviso = nivel_do_email(email)
    st.sidebar.caption(f"Conectado: {email}")
    st.sidebar.button("Sair", on_click=st.logout, key="btn_logout")
    if aviso:
        st.sidebar.warning(aviso)
    return Acesso(email, real, _escolher_nivel_exibido(real), True, aviso)
