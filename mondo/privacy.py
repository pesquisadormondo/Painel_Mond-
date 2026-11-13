"""Regras de privacidade (LGPD) aplicadas aos dados antes de chegarem aos níveis 1 e 2.

- faixas etárias no lugar de datas de nascimento;
- pseudonimização com HMAC-SHA256 (chave secreta guardada fora do banco);
- supressão de células pequenas (< k) para o nível público;
- k-anonimato por supressão local para os arquivos baixados por pesquisadores.

Atenção: dados pseudonimizados continuam sendo dados pessoais (LGPD, art. 13, §4º).
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import date

import numpy as np
import pandas as pd

AGE_EDGES = [0, 6, 12, 18, 30, 45, 60, 200]
AGE_LABELS = ["0–5", "6–11", "12–17", "18–29", "30–44", "45–59", "60+"]
AGE_COARSE = {
    "0–5": "0–17", "6–11": "0–17", "12–17": "0–17",
    "18–29": "18+", "30–44": "18+", "45–59": "18+", "60+": "18+",
}
TEXTO_LIVRE = ["outro_texto", "elogios_texto", "melhorias_texto", "intencao", "turno_preferido"]


# ------------------------------------------------------------------ idade
def idade_em(nascimento: pd.Series, ref: date) -> pd.Series:
    """Idade em anos completos na data de referência (NaN se faltar a data)."""
    n = pd.to_datetime(nascimento, errors="coerce")
    r = pd.Timestamp(ref)
    ainda_nao_fez = (n.dt.month > r.month) | ((n.dt.month == r.month) & (n.dt.day > r.day))
    anos = (r.year - n.dt.year) - ainda_nao_fez.astype(int)
    return anos.where(anos >= 0)


def faixa_etaria(idade: pd.Series) -> pd.Series:
    cat = pd.cut(idade, bins=AGE_EDGES, labels=AGE_LABELS, right=False)
    return cat.astype(object).where(cat.notna(), None)


# ------------------------------------------------------------------ pseudônimo
def _texto_id(v) -> str:
    if isinstance(v, (int, float, np.integer, np.floating)) and float(v).is_integer():
        return str(int(v))
    return str(v)


def pseudonimizar(valores: pd.Series, segredo: str, prefixo: str) -> pd.Series:
    """Código de 12 caracteres derivado por HMAC-SHA256. Mesmo valor + mesmo prefixo = mesmo código."""
    chave = segredo.encode("utf-8")

    def h(v):
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        msg = f"{prefixo}:{_texto_id(v)}".encode("utf-8")
        return hmac.new(chave, msg, hashlib.sha256).hexdigest()[:12]

    return valores.astype(object).map(h)


# ------------------------------------------------------------------ supressão
def suprimir(df: pd.DataFrame, col: str, k: int, complementar: bool = True) -> pd.DataFrame:
    """Marca como suprimidas as contagens entre 1 e k-1.

    complementar=True: se só UMA célula foi suprimida e o total é publicado, suprime também a
    menor célula restante, para que a diferença não revele o valor escondido.
    Devolve cópia com a coluna `suprimido` (bool) e NaN nas células suprimidas.
    """
    out = df.copy()
    out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")
    mask = (out[col] > 0) & (out[col] < k)
    if complementar and int(mask.sum()) == 1:
        restante = out.loc[~mask & (out[col] > 0), col]
        if len(restante):
            mask.loc[restante.idxmin()] = True
    out["suprimido"] = mask
    out.loc[mask, col] = np.nan
    return out


def texto_celula(valor, k: int) -> str:
    """Formata contagem em pt-BR; células suprimidas viram '<k'."""
    if valor is None or pd.isna(valor):
        return f"<{k}"
    return f"{valor:,.0f}".replace(",", ".")


# ------------------------------------------------------------------ k-anonimato
def passos_padrao(comunidade="comunidade", faixa="faixa_etaria", zona="zona", sexo="sexo"):
    """Ordem de generalização/supressão local: comunidade -> faixa etária grossa -> zona -> sexo."""
    return [
        (comunidade, lambda s: "Outras"),
        (faixa, lambda s: s.map(AGE_COARSE)),
        (zona, lambda s: np.nan),
        (sexo, lambda s: np.nan),
    ]


def aplicar_k_anonimato(df: pd.DataFrame, qi: list[str], k: int, passos=None):
    """Garante que cada combinação de quase-identificadores (qi) tenha ao menos k linhas.

    Generaliza ou apaga valores (supressão local) só nas linhas de grupos pequenos.
    Devolve (dataframe, relatório).
    """
    qi = [c for c in qi if c in df.columns]
    out = df.copy()
    for c in qi:
        out[c] = out[c].astype(object)

    def tamanhos(d):
        return d.groupby(qi, dropna=False)[qi[0]].transform("size")

    antes = tamanhos(out)
    relatorio = {
        "k": k,
        "linhas": int(len(out)),
        "menor_grupo_antes": int(antes.min()) if len(out) else 0,
        "linhas_em_grupos_pequenos_antes": int((antes < k).sum()),
    }
    for coluna, regra in (passos or passos_padrao()):
        if coluna not in qi:
            continue
        viol = tamanhos(out) < k
        if not viol.any():
            break
        novo = regra(out.loc[viol, coluna])
        out.loc[viol, coluna] = novo
    viol = tamanhos(out) < k
    if viol.any():  # último recurso: apaga todos os quase-identificadores dessas linhas
        out.loc[viol, qi] = np.nan
    depois = tamanhos(out)
    conhecidas = out[qi].notna().any(axis=1)  # linhas totalmente em branco não identificam ninguém
    igual = (df[qi].astype(object) == out[qi]) | (df[qi].isna() & out[qi].isna())
    relatorio.update(
        menor_grupo_depois=int(depois[conhecidas].min()) if conhecidas.any() else 0,
        linhas_alteradas=int((~igual.all(axis=1)).sum()),
    )
    return out, relatorio


# ------------------------------------------------------------------ frames por nível
def para_pesquisa(f: dict[str, pd.DataFrame], segredo: str, ref: date) -> dict[str, pd.DataFrame]:
    """Versão pseudonimizada e generalizada dos dados (usada nos níveis 1 e 2).

    Remove: nomes, CPF, telefone, endereço, coordenadas, nome do responsável/avaliador e textos livres.
    Substitui: ids de família, morador e participante por códigos HMAC. Nascimento -> faixa etária.
    """
    if not segredo:
        raise ValueError("Defina privacy.pseudo_secret (ou MONDO_PSEUDO_SECRET) para gerar dados pseudonimizados.")

    def P(s, prefixo):
        return pseudonimizar(s, segredo, prefixo)

    com = f["comunidade"].rename(columns={"nome": "comunidade"})[["id_comunidade", "comunidade"]]
    fam = f["familia"][["id_familia", "id_comunidade", "zona"]]

    mor = f["morador"].copy()
    mor["faixa_etaria"] = faixa_etaria(idade_em(mor["data_nascimento"], ref))
    tam = mor.groupby("id_familia").size().clip(upper=8).rename("n_moradores_familia")
    fam = fam.rename(columns={"id_comunidade": "id_com_fam", "zona": "zona_fam"})
    mor = mor.merge(fam, on="id_familia", how="left")
    # vale o território do próprio morador; se faltar (ex.: família não cadastrada), usa o da família
    for col, fb in (("id_comunidade", "id_com_fam"), ("zona", "zona_fam")):
        if col not in mor.columns:
            mor[col] = pd.NA
        mor[col] = mor[col].where(mor[col].notna(), mor[fb])
    mor = (mor.drop(columns=["id_com_fam", "zona_fam"])
              .merge(com, on="id_comunidade", how="left")
              .merge(tam, on="id_familia", how="left"))
    morador = pd.DataFrame({
        "id_morador": P(mor["id_morador"], "m"),
        "id_familia": P(mor["id_familia"], "f"),
        "sexo": mor["sexo"], "faixa_etaria": mor["faixa_etaria"],
        "ciclo": mor["ciclo"], "ipm": mor["ipm"], "status": mor["status"], "grupo": mor["grupo"],
        "comunidade": mor["comunidade"], "zona": mor["zona"],
        "n_moradores_familia": mor["n_moradores_familia"],
    })

    familia = pd.DataFrame({
        "id_familia": P(f["familia"]["id_familia"], "f"),
        "id_comunidade": f["familia"]["id_comunidade"],
        "zona": f["familia"]["zona"],
    })

    part = f["participante"]
    participante = pd.DataFrame({
        "id_participante": P(part["id_participante"], "p"),
        "id_morador": P(part["id_morador"], "m"),
        "origem": part["origem"],
    })

    pc = f["participacao"].copy()
    pc["id_participante"] = P(pc["id_participante"], "p")

    av = f["avaliacao"].drop(columns=["nome_avaliador"] + [c for c in TEXTO_LIVRE if c in f["avaliacao"].columns])
    av = av.copy()
    av["id_participante"] = P(av["id_participante"], "p")

    oferta = f["oferta"].drop(columns=[c for c in ["local", "descricao", "foto_coletiva", "link_documentacao"]
                                       if c in f["oferta"].columns])
    return {
        "dimensao": f["dimensao"], "categoria_atividade": f["categoria_atividade"],
        "comunidade": f["comunidade"], "item_doacao": f["item_doacao"],
        "atividade": f["atividade"], "oferta": oferta, "participacao": pc,
        "participante": participante, "morador": morador, "familia": familia, "avaliacao": av,
    }
