"""Níveis de acesso.

Nível 1 (público): sem login.
Nível 2 (pesquisador): login Google + e-mail na lista `access.researchers` (com validade opcional).
Nível 3 (administrador): login Google + e-mail na lista `access.admins`.

O login usa o recurso nativo do Streamlit (OpenID Connect com Google; seção [auth] do secrets.toml).
A autorização NÃO vem do Google: vem das listas abaixo (na fase do banco: tabela `acesso.acesso_pesquisador`).
Modo de desenvolvimento (dev.enabled = true): escolhe o nível sem login. Nunca ligue em produção.
"""
from __future__ import annotations

import hmac
import time
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


CABECALHOS_DE_PROXY = {"cf-connecting-ip", "cf-ray", "x-forwarded-for", "x-forwarded-host", "x-real-ip"}


def acesso_externo(cabecalhos) -> bool:
    """True se a requisição chegou por túnel/proxy (link externo) e não direto em localhost."""
    return bool({str(k).lower() for k in cabecalhos} & CABECALHOS_DE_PROXY)


LIMITE_FALHAS, JANELA_S = 8, 600  # 8 senhas erradas em 10 minutos (somando todas as sessões) bloqueiam o acesso


@st.cache_resource
def _falhas_de_senha() -> list:
    """Horários das tentativas erradas, compartilhados por todas as sessões do app."""
    return []


def portao_senha(settings) -> None:
    """Se access.team_password estiver definida, nada é carregado nem mostrado antes da senha correta.

    Proteção contra adivinhação: atraso crescente por sessão e bloqueio global após muitas falhas.
    """
    senha = getattr(settings, "team_password", None)
    if not senha or st.session_state.get("senha_ok"):
        return
    from . import audit, tema
    tema.tela_login("Instituto Mondó — painéis", "Acesso restrito à equipe do projeto.")
    _, centro, _ = st.columns([1, 1.3, 1])
    falhas = _falhas_de_senha()
    agora = time.time()
    falhas[:] = [t for t in falhas if agora - t < JANELA_S]
    if len(falhas) >= LIMITE_FALHAS:
        centro.error("Muitas tentativas incorretas. Aguarde alguns minutos e tente de novo.")
        st.stop()
    digitada = centro.text_input("Senha da equipe", type="password", key="senha_equipe")
    if digitada:
        if hmac.compare_digest(digitada.encode("utf-8"), str(senha).encode("utf-8")):
            st.session_state["senha_ok"] = True
            st.rerun()
        falhas.append(agora)
        tentativas = st.session_state.get("senha_erros", 0) + 1
        st.session_state["senha_erros"] = tentativas
        audit.registrar(settings, None, LEVEL_PUBLIC, "senha_incorreta", f"tentativa {tentativas}")
        time.sleep(min(2 * tentativas, 10))  # atrasa tentativas repetidas
        centro.error("Senha incorreta.")
    st.stop()


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


def nivel_do_email(email: str, hoje: date | None = None, settings=None) -> tuple[str, str | None]:
    """Devolve (nível, aviso) para um e-mail já autenticado.

    Administradores: só pela lista access.admins. Pesquisadores: se houver registro na tabela
    acesso.acesso_pesquisador (banco), ele decide (assim uma revogação vale mesmo que o e-mail ainda esteja
    na lista do secrets); sem registro, vale a lista access.researchers.
    """
    hoje = hoje or date.today()
    email = email.strip().lower()
    if email in _admins():
        return LEVEL_ADMIN, None
    if settings is not None:
        from . import acessos, db
        if db.usa_banco(settings):
            try:
                reg = acessos.buscar(settings, email)
            except Exception:
                reg = None  # banco indisponível: cai para a lista do secrets (falha segura = sem novos acessos)
            if reg is not None:
                ok, aviso = acessos.situacao(reg)
                return (LEVEL_RESEARCHER, None) if ok else (LEVEL_PUBLIC, aviso)
    pesq = _pesquisadores()
    if email in pesq:
        if _vigente(pesq[email], hoje):
            return LEVEL_RESEARCHER, None
        return LEVEL_PUBLIC, "Sua autorização de pesquisador expirou. Solicite renovação ao administrador."
    return LEVEL_PUBLIC, ("Esta conta não tem autorização para as áreas restritas. "
                          "Solicite acesso abaixo ou fale com o administrador do banco.")


def _escolher_nivel_exibido(real: str) -> str:
    opcoes = [n for n, o in LEVEL_ORDER.items() if o <= LEVEL_ORDER[real]]
    if len(opcoes) == 1:
        return real
    return st.sidebar.radio("Ver painéis como", opcoes, index=len(opcoes) - 1,
                            format_func=LEVEL_LABELS.get, key="ver_como",
                            help="Útil para conferir o que cada nível enxerga.")


def resolver_acesso(settings, mascarado: bool = False) -> Acesso:
    """`mascarado`: True quando os dados carregados têm identificações fictícias (ambiente de teste)."""
    if settings.dev_mode:
        st.sidebar.warning("Modo de desenvolvimento: login desativado.")
        nivel = st.sidebar.radio("Nível (dev)", list(LEVEL_LABELS), format_func=LEVEL_LABELS.get, key="dev_nivel")
        return Acesso("dev@local", nivel, nivel, nivel != LEVEL_PUBLIC)

    usuario = st.user
    logado = bool(getattr(usuario, "is_logged_in", False))
    if not logado:
        if secret("auth.client_id"):  # botão só aparece quando o login Google está configurado
            if st.sidebar.button("Entrar com Google", key="btn_login", type="primary"):
                try:
                    st.login()
                except Exception:
                    st.sidebar.error("Login Google não configurado. Veja a seção 'Login com Google' do README.")
            st.sidebar.caption("Sem login você vê apenas o painel público.")
        nivel_equipe = getattr(settings, "team_level", None)
        if (getattr(settings, "team_password", None) and st.session_state.get("senha_ok")
                and nivel_equipe in LEVEL_ORDER and nivel_equipe != LEVEL_PUBLIC):
            if nivel_equipe == LEVEL_ADMIN and not mascarado:
                # nunca entrega acesso total a dados reais por senha compartilhada
                st.sidebar.error("Nível de administrador por senha da equipe só é permitido com dados de TESTE "
                                 "(identificações fictícias). Para dados reais, use o login Google.")
            else:
                st.sidebar.caption("Acesso da equipe (senha compartilhada).")
                return Acesso("equipe (senha)", nivel_equipe, _escolher_nivel_exibido(nivel_equipe), True)
        return Acesso(None, LEVEL_PUBLIC, LEVEL_PUBLIC, False)

    email = str(usuario.get("email") or "").lower()
    if not usuario.get("email_verified", True):
        st.sidebar.error("O e-mail da conta Google não está verificado.")
        st.sidebar.button("Sair", on_click=st.logout, key="btn_logout")
        return Acesso(email, LEVEL_PUBLIC, LEVEL_PUBLIC, True, "E-mail não verificado.")

    real, aviso = nivel_do_email(email, settings=settings)
    st.sidebar.caption(f"Conectado: {email}")
    st.sidebar.button("Sair", on_click=st.logout, key="btn_logout")
    if aviso:
        st.sidebar.warning(aviso)
    if real == LEVEL_PUBLIC:
        from . import acessos, db
        if db.usa_banco(settings):
            acessos.formulario_solicitacao(settings, email)
    return Acesso(email, real, _escolher_nivel_exibido(real), True, aviso)
