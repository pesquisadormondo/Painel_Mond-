"""Contexto por nível de acesso e componentes de interface (filtros, gráficos, tabelas)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from .config import LEVEL_ADMIN, LEVEL_PUBLIC, LEVEL_RESEARCHER
from .privacy import AGE_LABELS, suprimir, texto_celula

PALETA = px.colors.qualitative.Safe
ORDENS = {"faixa_etaria": AGE_LABELS}


@dataclass
class Ctx:
    nivel: str
    k: int
    ref: date
    settings: object
    email: str | None
    frames: dict
    mor: pd.DataFrame
    fato_total: pd.DataFrame
    fato: pd.DataFrame
    av: pd.DataFrame
    qualidade: pd.DataFrame
    carregado_em: str
    filtros: dict = field(default_factory=dict)

    @property
    def publico(self) -> bool:
        return self.nivel == LEVEL_PUBLIC

    @property
    def restrito(self) -> bool:
        """Pesquisador ou administrador."""
        return self.nivel in (LEVEL_RESEARCHER, LEVEL_ADMIN)

    @property
    def admin(self) -> bool:
        return self.nivel == LEVEL_ADMIN

    def proteger(self, df: pd.DataFrame, col: str = "valor", complementar: bool = True) -> pd.DataFrame:
        """No nível público, suprime contagens < k; nos demais devolve os dados sem alteração."""
        if self.publico:
            return suprimir(df, col, self.k, complementar=complementar)
        out = df.copy()
        out["suprimido"] = False
        return out

    def n(self, v) -> str:
        """Número formatado; no nível público, valores entre 1 e k-1 viram '<k'."""
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        if self.publico and 0 < v < self.k:
            return f"<{self.k}"
        return f"{v:,.0f}".replace(",", ".")

    def aviso_supressao(self, df: pd.DataFrame) -> None:
        if self.publico and "suprimido" in df.columns and df["suprimido"].any():
            st.caption(f"Valores menores que {self.k} foram omitidos para proteger a privacidade (LGPD).")


# ------------------------------------------------------------------ filtros
def aplicar_filtros(fato_total: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Filtros da barra lateral (vazio = todos). Alteram só os painéis de atividades e participações."""
    with st.sidebar.expander("Filtros", expanded=False):
        anos = sorted(int(a) for a in fato_total["ano"].dropna().unique())
        sel_anos = st.multiselect("Ano", anos, placeholder="Todos", key="f_ano")
        dims = sorted(fato_total["dimensao"].dropna().unique())
        sel_dims = st.multiselect("Dimensão", dims, placeholder="Todas", key="f_dim")
        cats = sorted(fato_total["categoria"].dropna().unique())
        sel_cats = st.multiselect("Categoria", cats, placeholder="Todas", key="f_cat")
        base = fato_total
        if sel_dims:
            base = base[base["dimensao"].isin(sel_dims)]
        if sel_cats:
            base = base[base["categoria"].isin(sel_cats)]
        ativs = sorted(base["atividade"].dropna().unique())
        sel_ativs = st.multiselect("Atividade", ativs, placeholder="Todas", key="f_ativ")
    df = fato_total
    for col, sel in (("ano", sel_anos), ("dimensao", sel_dims), ("categoria", sel_cats), ("atividade", sel_ativs)):
        if sel:
            df = df[df[col].isin(sel)]
    return df, {"ano": sel_anos, "dimensao": sel_dims, "categoria": sel_cats, "atividade": sel_ativs}


# ------------------------------------------------------------------ gráficos e tabelas
def vazio(df: pd.DataFrame) -> bool:
    if df is None or len(df) == 0:
        st.info("Nenhum registro para os filtros selecionados.")
        return True
    return False


def barras(c: Ctx, df: pd.DataFrame, x: str, y: str = "valor", cor: str | None = None, titulo: str = "",
           horizontal: bool = False, empilhar: bool = False, rotulo_y: str = "", sensivel: bool = True) -> None:
    """`sensivel=False` desliga a supressão (use em números que não contam pessoas: ofertas, médias, %)."""
    if vazio(df):
        return
    d = c.proteger(df, y, complementar=cor is None) if sensivel else df.assign(suprimido=False)
    c.aviso_supressao(d)
    plot = d.dropna(subset=[y])
    if plot.empty:
        st.info("Todos os valores deste gráfico estão abaixo do mínimo de divulgação.")
        return
    if horizontal:
        plot = plot.sort_values(y)
    fig = px.bar(plot, x=y if horizontal else x, y=x if horizontal else y, color=cor, title=titulo,
                 orientation="h" if horizontal else "v", barmode="stack" if empilhar else "group",
                 category_orders={k: v for k, v in ORDENS.items() if k in (x, cor)},
                 color_discrete_sequence=PALETA, labels={y: rotulo_y or y})
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), legend_title_text="", template="plotly_white")
    st.plotly_chart(fig)


def rosca(c: Ctx, df: pd.DataFrame, nomes: str, valor: str = "valor", titulo: str = "") -> None:
    if vazio(df):
        return
    d = c.proteger(df, valor)
    c.aviso_supressao(d)
    plot = d.dropna(subset=[valor])
    if plot.empty:
        st.info("Todos os valores deste gráfico estão abaixo do mínimo de divulgação.")
        return
    fig = px.pie(plot, names=nomes, values=valor, hole=0.45, title=titulo, color_discrete_sequence=PALETA)
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), legend_title_text="")
    st.plotly_chart(fig)


def linhas_tempo(c: Ctx, df: pd.DataFrame, x: str, y: str = "valor", cor: str | None = None, titulo: str = "") -> None:
    if vazio(df):
        return
    d = c.proteger(df, y, complementar=False)
    c.aviso_supressao(d)
    plot = d.dropna(subset=[y])
    if plot.empty:
        st.info("Todos os valores deste gráfico estão abaixo do mínimo de divulgação.")
        return
    fig = px.bar(plot, x=x, y=y, color=cor, title=titulo, color_discrete_sequence=PALETA, barmode="stack")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), legend_title_text="", template="plotly_white")
    st.plotly_chart(fig)


def tabela(c: Ctx, df: pd.DataFrame, colunas_contagem: list[str] | None = None, **kwargs) -> None:
    """Mostra tabela; no nível público, contagens pequenas viram '<k' (supressão primária por coluna)."""
    if vazio(df):
        return
    out = df.copy()
    if c.publico:
        for col in colunas_contagem or []:
            s = suprimir(out, col, c.k, complementar=False)
            out[col] = s[col].map(lambda v: texto_celula(v, c.k))
    st.dataframe(out, hide_index=True, **kwargs)
