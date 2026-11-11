"""Instituto Mondó — painéis com 3 níveis de acesso (público, pesquisador, administrador).

Executar:  streamlit run app.py
"""
from __future__ import annotations

import secrets
from datetime import datetime

import streamlit as st

from mondo import audit, feedback, loader, pages
from mondo.auth import acesso_externo, portao_senha, resolver_acesso
from mondo.config import LEVEL_ADMIN, LEVEL_LABELS, get_settings
from mondo.metrics import avaliacao_enriquecida, fato_participacao, morador_enriquecido
from mondo.privacy import para_pesquisa
from mondo.ui import Ctx, aplicar_filtros

st.set_page_config(page_title="Instituto Mondó — Painéis", page_icon="📊", layout="wide")
settings = get_settings()

# Segurança: o modo de desenvolvimento libera todos os níveis sem login e NUNCA pode ser acessado por link externo.
if settings.dev_mode:
    try:
        externo = acesso_externo(st.context.headers)
    except Exception:
        externo = False
    if externo:
        st.error("Modo de desenvolvimento ligado e acesso por link externo detectado: app bloqueado por segurança. "
                 "Desligue dev.enabled (e a variável MONDO_DEV) e reinicie o app.")
        st.stop()

portao_senha(settings)  # se access.team_password estiver definida, nada abaixo roda antes da senha


# ------------------------------------------------------------------ dados (em cache)
def _versao_fonte() -> float:
    p = settings.xlsx_path
    return p.stat().st_mtime if settings.backend == "xlsx" and p and p.exists() else 0.0


@st.cache_resource(show_spinner="Carregando e organizando os dados…", ttl=6 * 3600)
def carregar_modelo(backend: str, caminho: str, url: str, versao: float, _settings):
    frames, qualidade, info = loader.carregar(_settings)
    return frames, qualidade, datetime.now().strftime("%d/%m/%Y %H:%M"), info


@st.cache_resource
def segredo_efemero() -> str:
    """Usado só quando não há chave configurada: vale enquanto o processo estiver no ar."""
    return secrets.token_hex(16)


@st.cache_resource(show_spinner="Aplicando regras de privacidade…")
def derivados(nivel: str, versao: float, ref_iso: str, segredo: str, _frames, _ref):
    frames = _frames if nivel == LEVEL_ADMIN else para_pesquisa(_frames, segredo, _ref)
    mor = morador_enriquecido(frames, _ref)
    return frames, mor, fato_participacao(frames, mor), avaliacao_enriquecida(frames)


try:
    frames_completos, qualidade, carregado_em, info_carga = carregar_modelo(
        settings.backend, str(settings.xlsx_path), str(settings.postgres_url or ""), _versao_fonte(), settings)
except (FileNotFoundError, ValueError) as erro:
    st.error(f"Não foi possível carregar os dados: {erro}")
    st.stop()

# ------------------------------------------------------------------ acesso
st.sidebar.markdown("### Instituto Mondó")
mascarado = bool(info_carga.get("mascarado"))
acesso = resolver_acesso(settings, mascarado)
nivel = acesso.nivel
st.sidebar.caption(f"Nível de acesso: **{LEVEL_LABELS[nivel]}**")
if mascarado:
    st.sidebar.info("🧪 **Ambiente de TESTE:** nomes, CPF, telefones, endereços e coordenadas são fictícios. "
                    "Os números (totais, atividades, participações, avaliações) são os da base.")

if acesso.logado and not st.session_state.get("login_registrado"):
    audit.registrar(settings, acesso.email, acesso.nivel_real, "login")
    st.session_state["login_registrado"] = True

segredo = settings.pseudo_secret or segredo_efemero()
if acesso.nivel_real == LEVEL_ADMIN and not settings.pseudo_secret:
    st.sidebar.warning("privacy.pseudo_secret não configurado: os códigos pseudônimos mudam a cada reinício.")

frames, mor, fato_total, av = derivados(nivel, _versao_fonte(), settings.ref_date.isoformat(), segredo,
                                        frames_completos, settings.ref_date)
fato, filtros = aplicar_filtros(fato_total)

ctx = Ctx(nivel=nivel, k=settings.k_min, ref=settings.ref_date, settings=settings, email=acesso.email,
          frames=frames, mor=mor, fato_total=fato_total, fato=fato, av=av, qualidade=qualidade,
          carregado_em=carregado_em, filtros=filtros)
# ------------------------------------------------------------------ navegação
PAGINAS_SENSIVEIS = {pages.saude, pages.doacoes}


def _rodar(fn):
    """Define o corte (k) conforme a página: sensíveis usam k_sensivel; as demais, k_min."""
    ctx.k = settings.k_sensivel if fn in PAGINAS_SENSIVEIS else settings.k_min
    fn(ctx)


P = lambda fn, titulo, icone, url, padrao=False: st.Page(lambda: _rodar(fn), title=titulo, icon=icone,
                                                         url_path=url, default=padrao)
menu = {"Painéis": [
    P(pages.visao_geral, "Visão geral", "🏠", "visao-geral", True),
    P(pages.atividades, "Atividades", "📅", "atividades"),
    P(pages.territorio, "Território", "📍", "territorio"),
    P(pages.perfil, "Perfil", "👥", "perfil"),
    P(pages.saude, "Saúde", "🩺", "saude"),
    P(pages.doacoes, "Doações e cestas", "🎁", "doacoes"),
    P(pages.avaliacoes, "Avaliações", "⭐", "avaliacoes"),
    P(pages.indicadores, "Indicadores", "📊", "indicadores"),
    P(pages.dados, "Dados: explorar e baixar", "⬇️", "dados"),
]}
if ctx.admin:
    menu["Administração"] = [
        P(pages.qualidade, "Qualidade dos dados", "🛠️", "qualidade"),
        P(pages.cadastro, "Consulta ao cadastro", "🔍", "cadastro"),
        P(pages.acessos, "Acessos e auditoria", "🔐", "acessos"),
        P(pages.feedback_admin, "Feedback da equipe", "💬", "feedback"),
    ]
menu["Informações"] = [P(pages.sobre, "Sobre estes dados", "ℹ️", "sobre")]

pagina = st.navigation(menu)
feedback.caixa(settings, pagina.title, filtros)
pagina.run()
