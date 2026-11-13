"""Tabelas derivadas e indicadores. Funciona com os dados completos (admin) e com os pseudonimizados."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .privacy import faixa_etaria, idade_em

NAO_INFORMADO = "Não informado"


def morador_enriquecido(f: dict[str, pd.DataFrame], ref: date) -> pd.DataFrame:
    """Morador com faixa etária, comunidade e zona (nos dados pseudonimizados já vêm prontos)."""
    mor = f["morador"].copy()
    if "faixa_etaria" not in mor.columns:
        mor["idade"] = idade_em(mor["data_nascimento"], ref)
        mor["faixa_etaria"] = faixa_etaria(mor["idade"])
    if "zona" not in mor.columns:
        com = f["comunidade"].rename(columns={"nome": "comunidade"})[["id_comunidade", "comunidade"]]
        fam = f["familia"][["id_familia", "id_comunidade", "zona"]]
        mor = mor.merge(fam, on="id_familia", how="left").merge(com, on="id_comunidade", how="left")
    return mor


def fato_participacao(f: dict[str, pd.DataFrame], mor: pd.DataFrame) -> pd.DataFrame:
    """Tabela plana: uma linha por participação, com atividade, dimensão, datas e perfil do participante."""
    p = f["participacao"]
    o = f["oferta"][["id_oferta", "id_atividade", "turma", "data_inicio", "data_fim"]]
    a = f["atividade"].rename(columns={"nome": "atividade"})[["id_atividade", "atividade", "id_dimensao", "id_categoria"]]
    d = f["dimensao"].rename(columns={"nome": "dimensao"})[["id_dimensao", "dimensao"]]
    c = f["categoria_atividade"].rename(columns={"nome": "categoria"})[["id_categoria", "categoria"]]
    it = f["item_doacao"].rename(columns={"nome": "item_doacao"})[["id_item_doacao", "item_doacao"]]
    com = f["comunidade"].rename(columns={"nome": "comunidade_atividade"})[["id_comunidade", "comunidade_atividade"]]
    part = f["participante"][["id_participante", "id_morador", "origem"]]
    demo = mor[["id_morador", "sexo", "faixa_etaria", "comunidade", "zona", "ciclo", "ipm", "status", "grupo"]].rename(
        columns={"comunidade": "comunidade_residencia", "zona": "zona_residencia"})

    out = (p.merge(o, on="id_oferta", how="left").merge(a, on="id_atividade", how="left")
            .merge(d, on="id_dimensao", how="left").merge(c, on="id_categoria", how="left")
            .merge(it, on="id_item_doacao", how="left").merge(com, on="id_comunidade", how="left")
            .merge(part, on="id_participante", how="left").merge(demo, on="id_morador", how="left"))
    out["ano"] = out["data_inicio"].dt.year
    out["mes"] = out["data_inicio"].dt.to_period("M").dt.to_timestamp()
    for col in ["sexo", "faixa_etaria", "comunidade_residencia", "zona_residencia", "comunidade_atividade",
                "item_doacao", "status"]:
        out[col] = out[col].astype(object).where(out[col].notna(), NAO_INFORMADO)
    return out.drop(columns=["id_comunidade"])


def contar(df: pd.DataFrame, por: list[str] | str, distinto: str | None = None, nome: str = "valor") -> pd.DataFrame:
    """Contagem de linhas (ou de valores distintos de `distinto`) por grupo."""
    por = [por] if isinstance(por, str) else por
    g = df.groupby(por, dropna=False, observed=True)
    s = g.size() if distinto is None else g[distinto].nunique()
    return s.rename(nome).reset_index()


def percentual(num: float, den: float) -> float | None:
    return None if not den else round(100 * num / den, 1)


def kpis(f: dict[str, pd.DataFrame], fato: pd.DataFrame, mor: pd.DataFrame) -> dict:
    ativos = mor[mor["status"] == "Ativa"]
    com_part = set(fato["id_morador"].dropna())
    return {
        "familias": int(f["familia"]["id_familia"].nunique()),
        "moradores_ativos": int(len(ativos)),
        "moradores_total": int(len(mor)),
        "participantes": int(fato["id_participante"].nunique()),
        "participacoes": int(len(fato)),
        "ofertas": int(fato["id_oferta"].nunique()),
        "atividades": int(fato["atividade"].nunique()),
        "cobertura_pct": percentual(int(ativos["id_morador"].isin(com_part).sum()), len(ativos)),
    }


# ------------------------------------------------------------------ avaliações
Q_COLS = {"q01_aprendizado": "Aprendizado", "q02_organizacao": "Organização", "q03_professores": "Professores",
          "q04_recomendacao": "Recomendaria", "q05_infraestrutura": "Infraestrutura", "q06_duracao": "Duração",
          "q07_informacoes_previas": "Informações prévias", "q08_material": "Material"}
INT_COLS = {"int_trabalhar_area": "Trabalhar na área", "int_primeiro_emprego": "Primeiro emprego",
            "int_mudar_area": "Mudar de área", "int_crescer_carreira": "Crescer na carreira",
            "int_abrir_negocio": "Abrir o próprio negócio", "int_renda_extra": "Aumentar a renda",
            "int_interesse_pessoal": "Interesse pessoal", "int_feiras_eventos": "Participar de feiras e eventos",
            "int_indeciso": "Ainda não sei", "int_outro": "Outro"}
TURNO_COLS = {"turno_manha": "Manhã", "turno_tarde": "Tarde", "turno_noite": "Noite",
              "turno_fim_semana": "Fim de semana"}


def avaliacao_enriquecida(f: dict[str, pd.DataFrame]) -> pd.DataFrame:
    d = f["dimensao"].rename(columns={"nome": "dimensao"})[["id_dimensao", "dimensao"]]
    return f["avaliacao"].merge(d, on="id_dimensao", how="left")


def medias_questoes(av: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for col, rotulo in Q_COLS.items():
        s = pd.to_numeric(av[col], errors="coerce").dropna()
        linhas.append({"questao": rotulo, "media": s.mean() if len(s) else np.nan, "respostas": int(len(s))})
    return pd.DataFrame(linhas)


def proporcoes(av: pd.DataFrame, colunas: dict[str, str]) -> pd.DataFrame:
    """Percentual de respostas 'sim' por opção (denominador: respostas com alguma opção preenchida)."""
    base = av[list(colunas)].notna().any(axis=1)
    n = int(base.sum())
    linhas = []
    for col, rotulo in colunas.items():
        marcados = int(av.loc[base, col].fillna(False).astype(bool).sum())
        linhas.append({"opcao": rotulo, "respondentes": marcados, "percentual": percentual(marcados, n)})
    return pd.DataFrame(linhas).sort_values("respondentes", ascending=False)


# ------------------------------------------------------------------ catálogo de indicadores
def catalogo(f, fato, mor, av, k: int, publico: bool) -> pd.DataFrame:
    """Valores dos indicadores candidatos (documentação, seção 8). Células públicas < k viram '<k'."""
    def n(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "—"
        if publico and 0 < v < k:
            return f"<{k}"
        return f"{v:,.0f}".replace(",", ".")

    def pct(v):
        return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.1f}%".replace(".", ",")

    kp = kpis(f, fato, mor)
    ativos = mor[mor["status"] == "Ativa"]
    menores = ativos["faixa_etaria"].isin(["0–5", "6–11", "12–17"]).sum()
    saude = fato[fato["dimensao"].astype(str).str.upper() == "SAÚDE"]
    nota = pd.to_numeric(av["nota_geral"], errors="coerce").dropna()
    q4 = pd.to_numeric(av["q04_recomendacao"], errors="coerce").dropna()
    intencoes = proporcoes(av, INT_COLS)
    turnos = proporcoes(av, TURNO_COLS)
    ipm = pd.to_numeric(mor["ipm"], errors="coerce").dropna()
    inativos = int((mor["status"] == "Inativa").sum())

    linhas = [
        ("IND-01", "Famílias cadastradas", n(kp["familias"]), "famílias", "P"),
        ("IND-02", "Moradores ativos", n(kp["moradores_ativos"]), "pessoas", "P"),
        ("IND-03", "Moradores ativos com menos de 18 anos", pct(percentual(int(menores), len(ativos))), "% dos ativos", "P"),
        ("IND-04", "Cobertura de atividades (ativos com ao menos 1 participação)", pct(kp["cobertura_pct"]), "% dos ativos", "P"),
        ("IND-05", "Participantes únicos", n(kp["participantes"]), "pessoas", "P"),
        ("IND-06", "Participações", n(kp["participacoes"]), "registros", "P"),
        ("IND-07", "Ofertas realizadas", n(kp["ofertas"]), "ofertas", "P"),
        ("IND-08", "Participações em atividades de saúde", n(len(saude)), "registros", "P"),
        ("IND-09a", "Participações com doação", n(int(fato["doacao"].sum())), "registros", "P"),
        ("IND-09b", "Participações com cesta básica", n(int(fato["cesta_basica"].sum())), "registros", "P"),
        ("IND-10", "Nota geral média das avaliações", "—" if nota.empty or (publico and len(nota) < k)
         else f"{nota.mean():.2f}".replace(".", ","), f"escala da planilha (n={n(len(nota))})", "P"),
        ("IND-11", "Recomendação: notas 4 e 5", "—" if q4.empty or (publico and len(q4) < k)
         else pct(percentual(int((q4 >= 4).sum()), len(q4))), f"% das respostas (n={n(len(q4))})", "P"),
        ("IND-12", "Intenção mais citada após a formação",
         "—" if intencoes.empty else f"{intencoes.iloc[0]['opcao']} ({pct(intencoes.iloc[0]['percentual'])})",
         "% dos respondentes", "P"),
        ("IND-13", "Turno preferido mais citado",
         "—" if turnos.empty else f"{turnos.iloc[0]['opcao']} ({pct(turnos.iloc[0]['percentual'])})",
         "% dos respondentes", "P"),
        ("IND-14", "IPM mediano dos moradores", "—" if ipm.empty else f"{ipm.median():.0f}", "valor da planilha (significado a confirmar)", "R"),
        ("IND-15", "Moradores inativos", pct(percentual(inativos, len(mor))), "% dos moradores", "R"),
    ]
    return pd.DataFrame(linhas, columns=["ID", "Indicador", "Valor", "Unidade / observação", "Nível mínimo"])
