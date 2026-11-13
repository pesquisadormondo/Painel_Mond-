"""Identidade visual do painel, alinhada ao BI "O Marajó em Dados" (Observatório Mondó).

Elementos do BI reproduzidos aqui:
- fundo de papel claro, com textura leve;
- barra de navegação marrom-cacau com a página ativa em mostarda (aqui, a barra lateral);
- cartões brancos de cantos arredondados, com uma barrinha vermelha antes do título;
- indicadores (st.metric) em cartões, número grande em marrom-escuro;
- gráficos em tons de marrom (barras de uma série: mais escuro = maior valor) e paleta terrosa para séries.

Uso: `cabecalho("Título", "subtítulo")` no começo de cada página (já chama `aplicar()`), e
`cartao("Título do gráfico")` para envolver gráficos. As cores do tema do Streamlit ficam em .streamlit/config.toml.
Para o logotipo, salve o arquivo em assets/logo_observatorio.png (ou .svg) na raiz do projeto.
"""
from __future__ import annotations

import base64
import html
from contextlib import contextmanager

import streamlit as st

from .config import ROOT

KICKER = "Instituto Mondó em dados"   # linha pequena acima do título, como "O MARAJÓ EM DADOS" no BI
LOGO_MENU = ROOT / "assets" / "logo_instituto_claro.png"   # logotipo claro, transparente, para a barra marrom
LOGOS = [ROOT / "assets" / "logo_observatorio.png", ROOT / "assets" / "logo_observatorio.svg"]

COR = {
    "papel": "#F4F1EC", "cacau": "#583A37", "ebano": "#3E1F1B", "mostarda": "#E8AE4F",
    "urucum": "#B8433E", "oliva": "#7C7240", "texto": "#3A2622", "borda": "#E6DED3", "grade": "#ECE5DB",
}
# séries categóricas (dimensões, categorias, sexo...): cores do BI, da mais viva para as neutras
PALETA = ["#B8433E", "#E8AE4F", "#7C7240", "#583A37", "#D9825E", "#A88F7F", "#3E1F1B", "#C9B29E"]
# barras de uma série: claro = menor valor, escuro = maior valor (como no gráfico de população do BI)
ESCALA_MARROM = ["#CDB7A3", "#A88F7F", "#8A6A5C", "#6B4B41", "#3E1F1B"]
FONTE_CORPO = "Barlow, 'Segoe UI', Helvetica, Arial, sans-serif"
FONTE_TITULO = "'Barlow Semi Condensed', Barlow, 'Segoe UI', Helvetica, Arial, sans-serif"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Semi+Condensed:wght@500;600;700&display=swap');

:root {
  --papel: #F4F1EC; --cacau: #583A37; --ebano: #3E1F1B; --mostarda: #E8AE4F; --urucum: #B8433E;
  --oliva: #7C7240; --texto: #3A2622; --borda: #E6DED3; --suave: #7A675C;
  --corpo: Barlow, 'Segoe UI', Helvetica, Arial, sans-serif;
  --titulo: 'Barlow Semi Condensed', Barlow, 'Segoe UI', Helvetica, Arial, sans-serif;
}

/* ---------- fundo de papel ---------- */
.stApp, [data-testid="stAppViewContainer"] {
  background-color: var(--papel);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='240'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 .35 0 0 0 0 .23 0 0 0 0 .2 0 0 0 .09 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}
[data-testid="stHeader"] { background: transparent; }
footer { visibility: hidden; }
.block-container { padding-top: 2rem; padding-bottom: 4rem; }

/* ---------- tipografia ---------- */
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stCaptionContainer"],
.stApp [data-testid="stWidgetLabel"], .stApp [data-baseweb="tab"], .stApp [data-baseweb="select"] {
  font-family: var(--corpo);
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
  font-family: var(--titulo); color: var(--ebano); letter-spacing: -0.005em;
}
.stApp h1 { font-weight: 700; font-size: 2.7rem; line-height: 1.05; padding: 0.2rem 0 0.4rem; }
.stApp h2 { font-weight: 700; }
.stApp h3 {
  font-weight: 600; font-size: 1.35rem;
  border-left: 5px solid var(--urucum); padding: 0.05rem 0 0.05rem 0.7rem; margin-top: 1.2rem;
}
.stApp [data-testid="stCaptionContainer"] { color: var(--suave); font-size: 1.02rem; }

/* ---------- cabeçalho de página ---------- */
.mondo-topo { display: flex; align-items: center; gap: 1rem; margin: 0 0 0.9rem; }
.mondo-logo img { height: 46px; display: block; }
.mondo-logo-texto { font-family: var(--titulo); line-height: .95; color: var(--cacau); }
.mondo-logo-texto small { display: block; font-size: .72rem; font-weight: 600; letter-spacing: .06em; }
.mondo-logo-texto strong { display: block; font-size: 1.9rem; font-weight: 700; letter-spacing: .07em; }
.mondo-divisor { width: 1px; align-self: stretch; background: var(--borda); min-height: 40px; }
.mondo-kicker {
  font-family: var(--titulo); font-weight: 700; font-size: .95rem; letter-spacing: .04em;
  text-transform: uppercase; color: var(--oliva);
}

/* ---------- barra lateral (a "barra marrom" do BI) ---------- */
[data-testid="stSidebar"] { background: var(--cacau); border-right: 0; }
[data-testid="stSidebar"] hr { border-color: rgba(244, 238, 230, .18); }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 { color: #F7F1E8; border-left: 0; padding-left: 0; }
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #D9C9B8; font-size: .92rem; }
[data-testid="stSidebarNavLink"] {
  border-radius: 10px; margin: 2px 0; font-weight: 600; color: #F4EEE6;
}
[data-testid="stSidebarNavLink"]:hover { background: rgba(255, 255, 255, .09); }
[data-testid="stSidebarNavLink"][aria-current="page"] { background: var(--mostarda); color: var(--ebano); }
[data-testid="stSidebarNavLink"][aria-current="page"] span,
[data-testid="stSidebarNavLink"][aria-current="page"] p { color: var(--ebano); font-weight: 700; }
[data-testid="stNavSectionHeader"], [data-testid="stNavSectionHeader"] span {
  color: #D9B77A; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; font-size: .78rem;
}
[data-testid="stSidebar"] [data-testid="stExpander"] details {
  border: 1px solid rgba(244, 238, 230, .25); border-radius: 12px; background: rgba(255, 255, 255, .04);
}

[data-testid="stSidebarHeader"] { padding-top: 1.4rem; padding-bottom: .6rem; }
[data-testid="stLogo"], [data-testid="stSidebarLogo"] { height: 3.6rem; max-width: 100%; }

/* ---------- cartões: gráficos e blocos com borda ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: #FFFFFF; border: 1px solid var(--borda); border-radius: 16px;
  box-shadow: 0 1px 3px rgba(62, 31, 27, .07); padding: 0.35rem 0.5rem;
}
.mondo-cartao-titulo {
  font-family: var(--titulo); font-weight: 600; font-size: 1.25rem; color: var(--ebano);
  border-left: 5px solid var(--urucum); border-radius: 2px; padding-left: .7rem; margin: .45rem 0 .2rem;
}

/* ---------- indicadores ---------- */
[data-testid="stMetric"] {
  background: #FFFFFF; border: 1px solid var(--borda); border-radius: 16px;
  box-shadow: 0 1px 3px rgba(62, 31, 27, .07); padding: 1rem 1.3rem;
}
[data-testid="stMetricLabel"] p { color: var(--suave); font-weight: 500; font-size: .98rem; }
[data-testid="stMetricValue"] {
  font-family: var(--titulo); font-weight: 600; color: var(--ebano); font-size: 2.5rem; line-height: 1.1;
}

/* ---------- abas, botões, campos, tabelas ---------- */
[data-baseweb="tab-list"] { gap: .4rem; border-bottom: 1px solid var(--borda); }
[data-baseweb="tab"] { font-weight: 600; color: var(--suave); }
[data-baseweb="tab"][aria-selected="true"] { color: var(--ebano); }
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"], .stFormSubmitButton > button {
  background: var(--mostarda); color: var(--ebano); border: 0; font-weight: 700; border-radius: 10px;
}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover,
.stFormSubmitButton > button:hover { background: #D99C3C; color: var(--ebano); }
.stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 600; }
[data-testid="stDataFrame"] { border: 1px solid var(--borda); border-radius: 12px; overflow: hidden; }
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stMain"] [data-testid="stExpander"] details {
  background: #FFFFFF; border: 1px solid var(--borda); border-radius: 12px;
}
</style>
"""


def aplicar() -> None:
    """Injeta o CSS do tema. Pode ser chamada em toda execução (só adiciona um bloco de estilo)."""
    st.markdown(CSS, unsafe_allow_html=True)
    if LOGO_MENU.exists():
        try:
            st.logo(str(LOGO_MENU), size="large")   # fica no topo do menu lateral
        except Exception:
            pass  # versões antigas do Streamlit não têm st.logo


# ------------------------------------------------------------------ cabeçalho e cartões
def _logo_html() -> str:
    for caminho in LOGOS:
        if caminho.exists():
            mime = "image/svg+xml" if caminho.suffix == ".svg" else "image/png"
            b64 = base64.b64encode(caminho.read_bytes()).decode()
            return f'<div class="mondo-logo"><img alt="Observatório Mondó" src="data:{mime};base64,{b64}"></div>'
    # sem arquivo de logotipo: assinatura em texto
    return '<div class="mondo-logo-texto"><small>OBSERVATÓRIO</small><strong>MONDÓ</strong></div>'


def cabecalho(titulo: str, subtitulo: str | None = None) -> None:
    """Topo da página: logotipo | linha pequena, título (st.title) e subtítulo (st.caption)."""
    aplicar()
    st.markdown(f'<div class="mondo-topo">{_logo_html()}<div class="mondo-divisor"></div>'
                f'<div class="mondo-kicker">{html.escape(KICKER)}</div></div>', unsafe_allow_html=True)
    st.title(titulo)
    if subtitulo:
        st.caption(subtitulo)


@contextmanager
def cartao(titulo: str = ""):
    """Cartão branco com título e barrinha vermelha, como os painéis do BI."""
    with st.container(border=True):
        if titulo:
            st.markdown(f'<div class="mondo-cartao-titulo">{html.escape(titulo)}</div>', unsafe_allow_html=True)
        yield


# ------------------------------------------------------------------ gráficos (Plotly)
def estilizar(fig, legenda_embaixo: bool = False) -> None:
    """Aplica o visual do BI a uma figura Plotly (fundo transparente, grade suave, fonte do tema)."""
    fig.update_layout(
        template="plotly_white", title=None,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONTE_CORPO, size=13, color=COR["texto"]),
        margin=dict(l=8, r=8, t=12, b=8), legend_title_text="", separators=",.", bargap=0.25,
        hoverlabel=dict(bgcolor="white", bordercolor=COR["borda"], font=dict(family=FONTE_CORPO, color=COR["texto"])),
    )
    if legenda_embaixo:
        fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.18, x=0))
    fig.update_xaxes(gridcolor=COR["grade"], linecolor=COR["borda"], zeroline=False, title_text=None)
    fig.update_yaxes(gridcolor=COR["grade"], linecolor=COR["borda"], zeroline=False)


GRAFICO_CONFIG = {"displayModeBar": False}  # sem a barra de ferramentas do Plotly, como no BI
