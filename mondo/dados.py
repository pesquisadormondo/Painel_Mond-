"""Tabelas para explorar e baixar (todos os níveis). Funções puras, sem Streamlit.

Regras por nível:
- Público: só tabelas AGREGADAS; contagens entre 1 e k-1 viram "<k" (k = privacy.k_explorador).
- Pesquisador: agregadas e MICRODADOS pseudonimizados; os filtros demográficos usam os valores já generalizados
  pelo k-anonimato, para que filtrar não revele o que foi escondido.
- Administrador: tudo, inclusive tabelas identificadas (CPF e telefone mascarados por padrão).
"""
from __future__ import annotations

import io

import pandas as pd

from .exportacao import COLS_MORADORES, DESCRICOES
from .privacy import aplicar_k_anonimato, passos_padrao

NAO_INFORMADO = "Não informado"
LIMITE_AGRUPAR_PUBLICO = 3

ROTULOS = {
    "ano": "Ano", "mes": "Mês", "dimensao": "Dimensão", "categoria": "Categoria", "atividade": "Atividade",
    "turma": "Turma", "tipo": "Tipo / módulo", "item_doacao": "Item de doação", "doacao": "Recebeu doação",
    "cesta_basica": "Recebeu cesta básica", "comunidade_atividade": "Comunidade (informada na atividade)",
    "sexo": "Sexo", "faixa_etaria": "Faixa etária", "comunidade_residencia": "Comunidade (residência)",
    "zona_residencia": "Zona (residência)", "origem": "Origem do participante", "status": "Situação",
    "ciclo": "Ciclo", "grupo": "Grupo", "ipm": "IPM", "comunidade": "Comunidade", "zona": "Zona",
    "evento": "Formação/evento", "formato": "Formato", "ano_formacao": "Ano da formação",
    "categoria_elogios": "Categoria do elogio", "categoria_melhorias": "Categoria da melhoria", "bairro": "Bairro",
}

# colunas disponíveis para "agrupar por" (base = todos os níveis; restrito = pesquisador e administrador)
AGRUPAR = {
    "participacoes": {
        "base": ["ano", "mes", "dimensao", "categoria", "atividade", "turma", "tipo", "item_doacao", "doacao",
                 "cesta_basica", "comunidade_atividade", "sexo", "faixa_etaria", "comunidade_residencia",
                 "zona_residencia", "origem"],
        "restrito": ["status", "ciclo", "grupo", "ipm"]},
    "moradores": {"base": ["sexo", "faixa_etaria", "comunidade", "zona", "status"], "restrito": ["ciclo", "grupo", "ipm"]},
    "avaliacoes": {"base": ["dimensao", "evento", "formato", "ano_formacao"],
                   "restrito": ["categoria_elogios", "categoria_melhorias"]},
}
FILTROS = {
    "participacoes": ["ano", "dimensao", "categoria", "atividade", "tipo", "turma", "sexo", "faixa_etaria",
                      "comunidade_residencia", "zona_residencia", "origem"],
    "moradores": ["sexo", "faixa_etaria", "comunidade", "zona", "status"],
    "avaliacoes": ["dimensao", "evento", "formato", "ano_formacao"],
}
FILTROS_RESTRITOS = {"participacoes": ["status", "ciclo", "grupo"], "moradores": ["ciclo", "grupo"], "avaliacoes": []}

# medida -> (rótulo, regra, é_contagem_de_pessoas_ou_registros)
MEDIDAS = {
    "participacoes": {
        "participacoes": ("Participações", "size", True),
        "participantes": ("Participantes únicos", "nunique:id_participante", True),
        "ofertas": ("Ofertas", "nunique:id_oferta", False),
        "doacoes": ("Participações com doação", "sum:doacao", True),
        "cestas": ("Participações com cesta básica", "sum:cesta_basica", True)},
    "moradores": {
        "moradores": ("Moradores", "size", True),
        "familias": ("Famílias", "nunique:id_familia", True),
        "ipm_medio": ("IPM médio", "mean:ipm", False)},
    "avaliacoes": {
        "respostas": ("Respostas", "size", True),
        "nota_media": ("Nota geral média", "mean:nota_geral", False),
        "recomendacao_media": ("Recomendação (média da pergunta 4)", "mean:q04_recomendacao", False),
        "recomendam_pct": ("% que recomendam (notas 4 e 5)", "pct4:q04_recomendacao", False)},
}


# ------------------------------------------------------------------ agregação
def _calcular(sub: pd.DataFrame, regra: str):
    tipo, _, col = regra.partition(":")
    if tipo == "size":
        return len(sub)
    if tipo == "nunique":
        return int(sub[col].nunique())
    if tipo == "sum":
        return int(sub[col].fillna(False).astype(bool).sum())
    s = pd.to_numeric(sub[col], errors="coerce").dropna()
    if tipo == "mean":
        return round(float(s.mean()), 2) if len(s) else None
    if tipo == "pct4":
        return round(100 * float((s >= 4).mean()), 1) if len(s) else None
    raise ValueError(regra)


def chave_texto(d: pd.DataFrame, col: str) -> pd.Series:
    """Coluna como texto legível (anos sem ".0", booleanos como Sim/Não, vazio como "Não informado")."""
    s = d[col]
    if col == "mes":
        s = s.dt.strftime("%Y-%m")
    elif pd.api.types.is_bool_dtype(s) or str(s.dtype) == "boolean":
        s = s.map({True: "Sim", False: "Não"})
    elif pd.api.types.is_numeric_dtype(s):
        s = s.map(lambda v: None if pd.isna(v) else (str(int(v)) if float(v).is_integer() else str(v)))
    return s.astype(object).where(s.notna(), NAO_INFORMADO)


def agregar(df: pd.DataFrame, fonte: str, por: list[str], medidas: list[str]) -> pd.DataFrame:
    """Tabela agregada. Inclui a coluna técnica `__n` (linhas no grupo), usada na supressão pública."""
    d = df.copy()
    for col in por:
        d[col] = chave_texto(d, col)
    itens = [((), d)] if not por else d.groupby(por, dropna=False, sort=True)
    linhas = []
    for chave, sub in itens:
        chave = chave if isinstance(chave, tuple) else (chave,)
        linha = dict(zip(por, chave))
        linha["__n"] = len(sub)
        for m in medidas:
            linha[m] = _calcular(sub, MEDIDAS[fonte][m][1])
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=por + ["__n"] + medidas)


def suprimir_publico(tab: pd.DataFrame, fonte: str, medidas: list[str], k: int) -> pd.DataFrame:
    """Contagens de 1 a k-1 viram '<k'; médias e percentuais de grupos com menos de k linhas também."""
    out = tab.astype(object).copy()
    pequeno = (tab["__n"] > 0) & (tab["__n"] < k)
    rotulo = f"<{k}"
    for m in medidas:
        if MEDIDAS[fonte][m][2]:
            v = pd.to_numeric(tab[m], errors="coerce")
            out.loc[(v > 0) & (v < k), m] = rotulo
        else:
            out.loc[pequeno, m] = rotulo
    return out


def finalizar(tab: pd.DataFrame, fonte: str, por: list[str], medidas: list[str]) -> pd.DataFrame:
    """Remove a coluna técnica e troca nomes de colunas por rótulos em português."""
    out = tab.drop(columns=["__n"])
    nomes = {c: ROTULOS.get(c, c) for c in por}
    nomes.update({m: MEDIDAS[fonte][m][0] for m in medidas})
    return out.rename(columns=nomes)


# ------------------------------------------------------------------ microdados pseudonimizados
def preparar_microdados(mor_p: pd.DataFrame, fato_p: pd.DataFrame, av_p: pd.DataFrame, part_p: pd.DataFrame, k: int):
    """Devolve (moradores_k, participacoes_k, avaliacoes) com k-anonimato nos quase-identificadores.

    As participações recebem sexo, faixa etária, comunidade e zona dos valores JÁ generalizados do arquivo de moradores.
    """
    moradores_k, rel = aplicar_k_anonimato(mor_p[COLS_MORADORES], ["comunidade", "faixa_etaria", "sexo", "zona"],
                                           k, passos_padrao())
    demo = moradores_k[["id_morador", "sexo", "faixa_etaria", "comunidade", "zona"]].rename(
        columns={"comunidade": "comunidade_residencia", "zona": "zona_residencia"})
    base = fato_p.drop(columns=["sexo", "faixa_etaria", "comunidade_residencia", "zona_residencia"])
    part_k = base.merge(demo, on="id_morador", how="left")
    for col in ["sexo", "faixa_etaria", "comunidade_residencia", "zona_residencia"]:
        part_k[col] = part_k[col].astype(object).where(part_k[col].notna(), NAO_INFORMADO)
    av = av_p.merge(part_p[["id_participante", "id_morador"]], on="id_participante", how="left", suffixes=("", "_p"))
    if "id_morador" not in av.columns:
        av["id_morador"] = None
    av["ano_formacao"] = av["data_formacao"].dt.year
    return moradores_k, part_k, av, rel


# ------------------------------------------------------------------ identificação (somente administrador)
def mascarar(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "cpf" in out:
        out["cpf"] = out["cpf"].map(lambda v: f"***.{v[3:6]}.{v[6:9]}-**" if isinstance(v, str) and len(v) == 11 else None)
    if "telefone" in out:
        out["telefone"] = out["telefone"].map(lambda v: f"(**) *****-{v[-4:]}" if isinstance(v, str) and len(v) >= 4 else None)
    return out


# ------------------------------------------------------------------ exportação
FORMATOS = ["CSV (vírgula, UTF-8)", "CSV para Excel (ponto e vírgula)", "Excel (.xlsx)"]


def exportar(df: pd.DataFrame, formato: str) -> tuple[bytes, str, str]:
    """Devolve (bytes, mime, extensão)."""
    if formato == FORMATOS[0]:
        return df.to_csv(index=False, date_format="%Y-%m-%d").encode("utf-8"), "text/csv", "csv"
    if formato == FORMATOS[1]:
        return (df.to_csv(index=False, sep=";", decimal=",", date_format="%Y-%m-%d").encode("utf-8-sig"),
                "text/csv", "csv")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="dados")
    return buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"


def dicionario_csv(colunas) -> bytes:
    linhas = [{"coluna": c, "descricao": DESCRICOES.get(c, "")} for c in colunas]
    return pd.DataFrame(linhas).to_csv(index=False).encode("utf-8")

