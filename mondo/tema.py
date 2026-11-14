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
from pathlib import Path
from contextlib import contextmanager

import streamlit as st

from .config import ROOT

KICKER = "Instituto Mondó em dados"   # linha pequena acima do título, como "O MARAJÓ EM DADOS" no BI
LOGO_MENU = ROOT / "assets" / "logo_instituto_claro.png"   # logotipo claro, transparente, para a barra marrom
CAPA_GIF = ROOT / "assets" / "capa_login.gif"     # animação que toca uma vez e para no último quadro
CAPA_LOGIN = ROOT / "assets" / "capa_login.webp"  # imagem estática (usada se não houver o GIF)
ICONES_DIR = ROOT / "assets" / "icones_menu"
VAZIO_IMG = ROOT / "assets" / "ilustracao_vazio.webp"   # ilustração das telas vazias

# ---- Rodapé: faixa vermelha fixa em todas as páginas ----
RODAPE_TEXTO = "<b>INSTITUTO MONDÓ.</b> Todos os direitos reservados."   # o "©" e o ano são colocados automaticamente
RODAPE_EM_TODAS_AS_PAGINAS = True     # False: só em "Sobre estes dados"
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
  border-left: 5px solid var(--urucum); padding: 0.05rem 0 0.05rem 0.7rem; margin: 1.2rem 0 .9rem;
}
[data-baseweb="tab-panel"] { padding-top: 1.1rem; }
[data-testid="stSelectbox"], [data-testid="stMultiSelect"], [data-testid="stRadio"] { margin-bottom: .35rem; }
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

/* ---------- tela de login ---------- */
.mondo-capa { max-width: 980px; margin: 0 auto 1.2rem; }
.mondo-capa img { width: 100%; height: auto; display: block; }
.mondo-login-titulo { text-align: center; margin: 0 0 .2rem; }
.mondo-login-titulo h1 { font-size: 2.2rem; padding: 0; margin: 0; }
.mondo-login-sub { text-align: center; color: var(--suave); margin: 0 0 1.2rem; font-size: 1.05rem; }

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

/* ---------- alertas na paleta do projeto ---------- */
[data-testid="stAlert"] [data-baseweb="notification"] {
  background-color: #FBECE9 !important; border: 1px solid #EBC9C4 !important; border-left: 5px solid var(--urucum) !important;
  border-radius: 12px !important; color: #5E1F1B !important;
}
[data-testid="stAlert"] [data-baseweb="notification"] * { color: #5E1F1B; }
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) [data-baseweb="notification"] {
  background-color: #FCF3DF !important; border-color: #F0DAA8 !important; border-left-color: var(--mostarda) !important;
}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) [data-baseweb="notification"] * { color: #5A4010; }
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) [data-baseweb="notification"] {
  background-color: #F1F1E3 !important; border-color: #D8D6B0 !important; border-left-color: var(--oliva) !important;
}
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) [data-baseweb="notification"] * { color: #44401F; }
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) [data-baseweb="notification"] {
  background-color: #F6D9D5 !important; border-color: #E3A9A2 !important; border-left-color: #8E2F2A !important;
}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) [data-baseweb="notification"] * { color: #5A1612; }
[data-testid="stMain"] [data-testid="stExpander"] details {
  background: #FFFFFF; border: 1px solid var(--borda); border-radius: 12px;
}
/* ---------- indicadores com ícone (compactos) ---------- */
.mondo-kpi {
  display: flex; align-items: center; gap: .8rem; background: #FFFFFF; border: 1px solid var(--borda);
  border-radius: 14px; box-shadow: 0 1px 2px rgba(62, 31, 27, .06); padding: 0 1rem; height: 5rem;
  box-sizing: border-box; margin-bottom: .7rem;     /* compensa o espaço negativo que o st.markdown aplica */
}
.mondo-kpi-icone {
  flex: 0 0 2.7rem; width: 2.7rem; height: 2.7rem; border-radius: 10px; background: #F7ECDD;
  display: flex; align-items: center; justify-content: center;
}
.mondo-kpi-icone img { width: 1.5rem; height: 1.5rem; display: block; }
.mondo-kpi-texto { flex: 1; min-width: 0; text-align: center; }
.mondo-kpi-rotulo {
  color: var(--suave); font-size: .82rem; font-weight: 500; line-height: 1.15; min-height: 2.3em;
  display: flex; align-items: flex-end; justify-content: center;   /* rótulos de 1 ou 2 linhas: número sempre na mesma altura */
}
.mondo-kpi-valor { font-family: var(--titulo); font-weight: 600; color: var(--ebano); font-size: 1.95rem; line-height: 1.05; margin-top: .05rem; }
[data-testid="stHorizontalBlock"]:has(.mondo-kpi) { gap: .7rem; }

/* ---------- tela vazia ---------- */
.mondo-vazio {
  text-align: center; padding: 1.8rem 1rem 1.6rem; background: rgba(255, 255, 255, .6);
  border: 1px dashed #D9CCBB; border-radius: 16px; margin: .8rem 0 1.6rem;
}
.mondo-vazio img { height: 120px; width: auto; display: block; margin: 0 auto .6rem; }
.mondo-vazio-titulo { font-family: var(--titulo); font-weight: 600; font-size: 1.35rem; color: var(--ebano); }
.mondo-vazio-dica { color: var(--suave); font-size: 1.02rem; margin-top: .2rem; }
[data-testid="stSpinner"] { color: var(--cacau); font-weight: 600; }

/* ---------- rodapé: faixa vermelha fina, fixa no fim da tela ---------- */
.mondo-rodape {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 1000001;       /* acima da barra lateral */
  background: #B33636; color: #FAEBD7; text-align: center; padding: .28rem 1rem; font-size: .78rem; line-height: 1.3;
  box-shadow: 0 -1px 6px rgba(35, 15, 5, .2);
}
.mondo-rodape b { font-weight: 700; }
@media (max-width: 640px) { .mondo-rodape { font-size: .7rem; padding: .25rem .6rem; } }

/* ---------- celular ---------- */
@media (max-width: 640px) {
  .block-container { padding: 1rem .8rem 3.4rem !important; }
  .stApp h1 { font-size: 2rem; }
  .stApp h3 { font-size: 1.15rem; margin: 1rem 0 .7rem; }
  .mondo-topo { gap: .7rem; flex-wrap: wrap; }
  .mondo-logo img { height: 34px; }
  .mondo-logo-texto strong { font-size: 1.5rem; }
  .mondo-kicker { font-size: .8rem; }
  /* indicadores: 2 por linha, em vez de um embaixo do outro */
  [data-testid="stHorizontalBlock"]:has(.mondo-kpi) { flex-wrap: wrap !important; gap: .5rem !important; }
  [data-testid="stHorizontalBlock"]:has(.mondo-kpi) > [data-testid="stColumn"],
  [data-testid="stHorizontalBlock"]:has(.mondo-kpi) > [data-testid="column"] {
    flex: 0 0 calc(50% - .25rem) !important; min-width: calc(50% - .25rem) !important; width: calc(50% - .25rem) !important;
  }
  .mondo-kpi { height: auto; min-height: 4.4rem; padding: .45rem .6rem; gap: .5rem; margin-bottom: .4rem; }
  .mondo-kpi-icone { flex-basis: 2rem; width: 2rem; height: 2rem; border-radius: 8px; }
  .mondo-kpi-icone img { width: 1.15rem; height: 1.15rem; }
  .mondo-kpi-rotulo { font-size: .72rem; min-height: 0; }
  .mondo-kpi-valor { font-size: 1.55rem; }
  /* menu e abas mais fáceis de tocar */
  [data-testid="stSidebarNavLink"] { min-height: 2.9rem; }
  [data-baseweb="tab"] { padding: .45rem .7rem; font-size: .92rem; }
  .mondo-vazio { padding: 1.2rem .8rem; }
  .mondo-vazio img { height: 90px; }
  .mondo-login-titulo h1 { font-size: 1.7rem; }
}
</style>
"""


@st.cache_data(show_spinner=False)
def _css_feedback() -> str:
    """Ícone de assets/icones_menu/feedback.png (ou feedback_admin.png) no título do expander "Enviar feedback"."""
    for nome in ("feedback", "feedback_admin"):
        arq = ICONES_DIR / f"{nome}.png"
        if arq.exists():
            return ('<style>.st-key-caixa_feedback summary [data-testid="stMarkdownContainer"] p::before { '
                    'content: ""; display: inline-block; width: 1.35rem; height: 1.35rem; margin-right: .55rem; '
                    f'vertical-align: -0.3rem; background: url("data:image/png;base64,{_b64(str(arq))}") '
                    'center / contain no-repeat; }</style>')
    return ""


@st.cache_data(show_spinner=False)
def _css_icones() -> str:
    """Troca o emoji de cada item do menu lateral pela imagem de assets/icones_menu/<endereço-da-página>.<ext>.

    O nome do arquivo é o endereço (url_path) da página: atividades.png, saude.svg, doacoes.webp...
    Aceita png, svg, webp e jpg. Páginas sem arquivo continuam com o ícone padrão do Streamlit.
    """
    regras = ['[data-testid="stSidebarNavLink"] { padding: .3rem .45rem; gap: 0; align-items: center; }']
    if not ICONES_DIR.exists():
        return ""
    mimes = {".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp", ".jpg": "image/jpeg",
             ".jpeg": "image/jpeg"}
    for arq in sorted(ICONES_DIR.iterdir()):
        mime = mimes.get(arq.suffix.lower())
        if not mime or arq.name.startswith("."):
            continue
        pagina = arq.stem
        # "contém /nome" (sem diferenciar maiúsculas) aceita /feedback, /feedback_admin, /Feedback_da_equipe...
        alvos = [f'[href*="/{pagina}" i]']
        if pagina == "visao_geral":
            alvos.append('[href$="/"]')   # a página inicial tem o endereço "/"
        for alvo in alvos:
            link = f'a[data-testid="stSidebarNavLink"]{alvo}'
            regras.append(f'{link} [data-testid="stIconEmoji"], {link} [data-testid="stIconMaterial"] '
                          f'{{ display: none; }}')
            regras.append(f'{link}::before {{ content: ""; flex: 0 0 auto; width: 2.15rem; height: 2.15rem; '
                          f'margin-right: .7rem; border-radius: 10px; '
                          f'background: url("data:{mime};base64,{_b64(str(arq))}") center / contain no-repeat; }}')
    return "<style>" + "\n".join(regras) + "</style>" if len(regras) > 1 else ""


def aplicar(logo: bool = True) -> None:
    """Injeta o CSS do tema. Pode ser chamada em toda execução (só adiciona um bloco de estilo).

    `logo=False` não coloca o logotipo no topo do menu lateral (usado na tela de senha, que não tem menu)."""
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        css_icones = _css_icones()
        if css_icones:
            st.markdown(css_icones, unsafe_allow_html=True)
        css_fb = _css_feedback()
        if css_fb:
            st.markdown(css_fb, unsafe_allow_html=True)
    except Exception:
        pass  # ícones são enfeite: nunca podem derrubar a página
    if logo and LOGO_MENU.exists():
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


@st.cache_data(show_spinner=False)
def _b64(caminho: str) -> str:
    return base64.b64encode(Path(caminho).read_bytes()).decode()


def _imagem_na_coluna(caminho: str) -> None:
    """Mostra a imagem ocupando toda a largura da coluna (assim ela fica centralizada junto com a coluna)."""
    try:
        st.image(caminho, width="stretch")
    except Exception:            # versões mais antigas do Streamlit
        st.image(caminho, use_container_width=True)


def tela_login(titulo: str, subtitulo: str) -> None:
    """Topo da tela de senha: ilustração do Observatório, título e subtítulo centralizados, sem barra lateral."""
    aplicar(logo=False)
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], "
                "[data-testid='stExpandSidebarButton'], [data-testid='stLogo'], [data-testid='stSidebarLogo'], "
                "[data-testid='stHeaderLogo'] { display: none !important; } "
                "[data-testid='stImage'] img { mix-blend-mode: multiply; }</style>", unsafe_allow_html=True)
    capa = CAPA_GIF if CAPA_GIF.exists() else CAPA_LOGIN
    if capa.exists():
        # o fundo branco da animação se funde ao papel da página (mix-blend-mode: multiply, definido no CSS)
        _, meio, _ = st.columns([2, 5, 2])      # imagem com cerca de 55% da largura
        with meio:
            _imagem_na_coluna(str(capa))
    st.markdown(f'<div class="mondo-login-titulo"><h1>{html.escape(titulo)}</h1></div>'
                f'<p class="mondo-login-sub">{html.escape(subtitulo)}</p>', unsafe_allow_html=True)
    rodape()          # faixa vermelha fixa também nas telas de senha e de entrada


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
        margin=dict(l=8, r=8, t=12, b=8), legend_title_text="", separators=",.", bargap=0.35,
        hoverlabel=dict(bgcolor="white", bordercolor=COR["borda"], font=dict(family=FONTE_CORPO, color=COR["texto"])),
    )
    if legenda_embaixo:
        fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.18, x=0))
    fig.update_xaxes(gridcolor=COR["grade"], linecolor=COR["borda"], zeroline=False, title_text=None)
    fig.update_yaxes(gridcolor=COR["grade"], linecolor=COR["borda"], zeroline=False, title_text=None)


GRAFICO_CONFIG = {"displayModeBar": False}  # sem a barra de ferramentas do Plotly, como no BI


# ------------------------------------------------------------------ ícones dos indicadores (traço simples, desenho próprio)
_ICONES_SVG = {
    "casa": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "pessoas": '<path d="M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20"/><circle cx="10" cy="8" r="3.5"/>'
               '<path d="M20 20v-1.5a3.5 3.5 0 0 0-2.5-3.35"/><path d="M15.5 4.65a3.5 3.5 0 0 1 0 6.7"/>',
    "pessoa": '<circle cx="12" cy="8" r="3.8"/><path d="M4.5 20.5v-1a5 5 0 0 1 5-5h5a5 5 0 0 1 5 5v1"/>',
    "calendario": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    "prancheta": '<rect x="5" y="4" width="14" height="17" rx="2.5"/><path d="M9 4V3h6v1"/><path d="M8.5 13l2.5 2.5 4.5-5"/>',
    "alvo": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
    "atividade": '<path d="M3 12h4l2.5-7 5 14L17 12h4"/>',
    "presente": '<rect x="3.5" y="9" width="17" height="4" rx="1"/><path d="M5 13v7.5h14V13M12 9v11.5"/>'
                '<path d="M12 9c-1.5-4-6-4-5-.5S12 9 12 9zm0 0c1.5-4 6-4 5-.5S12 9 12 9z"/>',
    "cesta": '<path d="M5 8h14l-1.2 11.5H6.2z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>',
    "estrela": '<path d="M12 3.5l2.6 5.3 5.9.85-4.25 4.15 1 5.85L12 16.9 6.75 19.65l1-5.85L3.5 9.65l5.9-.85z"/>',
    "joinha": '<path d="M7 11v9H4v-9z"/><path d="M7 11l4-7c1.7 0 2.5 1.3 2.2 2.8L12.7 10H19a2 2 0 0 1 2 2.4l-1.3 6A2 2 0 0 1 17.7 20H7"/>',
    "balao": '<path d="M20.5 12a8 8 0 0 1-11.7 7.1L4 20.5l1.4-4.3A8 8 0 1 1 20.5 12z"/>',
    "alerta": '<path d="M12 3.5l9.5 16.5h-19z"/><path d="M12 10v4.5M12 17.3v.2"/>',
    "grafico": '<path d="M4 20V4"/><path d="M4 20h16"/><path d="M8 16v-5M12 16V8M16 16v-8"/>',
}
def _svg_uri(corpo: str, cor: str = "#583A37", traco: float = 1.8) -> str:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
           f'stroke-width="{traco}" stroke-linecap="round" stroke-linejoin="round">{corpo}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode()


def kpi(rotulo: str, valor, icone: str = "grafico", ajuda: str | None = None, onde=None) -> None:
    """Indicador em cartão: quadradinho creme com ícone + rótulo + número grande (como nos cartões do BI).

    `onde`: coluna (k1, k2...) em que desenhar; sem ela, desenha onde estiver o cursor da página.
    """
    uri = _svg_uri(_ICONES_SVG.get(icone, _ICONES_SVG["grafico"]))
    dica = f' title="{html.escape(ajuda, quote=True)}"' if ajuda else ""
    (onde or st).markdown(
        f'<div class="mondo-kpi"{dica}><div class="mondo-kpi-icone"><img alt="" src="{uri}"></div>'
        f'<div class="mondo-kpi-texto"><div class="mondo-kpi-rotulo">{html.escape(str(rotulo))}</div>'
        f'<div class="mondo-kpi-valor">{html.escape(str(valor))}</div></div></div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ telas vazias, carregamento, capa
def vazio_amigavel(titulo: str = "Nada encontrado por aqui", dica: str | None = None) -> None:
    """Mensagem amigável com a ilustração do Observatório (no lugar de um aviso azul seco)."""
    img = ""
    if VAZIO_IMG.exists():
        img = f'<img alt="" src="data:image/webp;base64,{_b64(str(VAZIO_IMG))}">'
    extra = f'<div class="mondo-vazio-dica">{html.escape(dica)}</div>' if dica else ""
    st.markdown(f'<div class="mondo-vazio">{img}<div class="mondo-vazio-titulo">{html.escape(titulo)}</div>{extra}</div>',
                unsafe_allow_html=True)


@contextmanager
def carregando(texto: str = "Carregando os dados do Instituto Mondó…"):
    """Use em volta de trabalhos demorados: `with tema.carregando(): dados = carregar(...)`."""
    with st.spinner(texto):
        yield


def capa_pagina() -> None:
    """Animação do Observatório no topo de uma página (a mesma da tela de login: toca uma vez e fica parada)."""
    capa = CAPA_GIF if CAPA_GIF.exists() else CAPA_LOGIN
    if capa.exists():
        st.markdown("<style>[data-testid='stImage'] img { mix-blend-mode: multiply; }</style>", unsafe_allow_html=True)
        _, meio, _ = st.columns([2, 5, 2])      # mesmo tamanho da tela de login
        with meio:
            _imagem_na_coluna(str(capa))


# ------------------------------------------------------------------ rodapé
@st.cache_data(show_spinner=False)
def _rodape_html() -> str:
    from datetime import date
    # reserva espaço no fim da página e do menu lateral, para a faixa fixa não esconder nada
    reserva = ("<style>.block-container{padding-bottom:3.4rem !important}"
               "[data-testid='stSidebarContent']{padding-bottom:3rem}</style>")
    return f'{reserva}<div class="mondo-rodape">©{date.today().year} {RODAPE_TEXTO}</div>'


def rodape() -> None:
    """Faixa vermelha fixa no fim da tela, com o direito autoral."""
    st.markdown(_rodape_html(), unsafe_allow_html=True)
