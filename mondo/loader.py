"""Carrega os dados e devolve o modelo v0.3 (tabelas e colunas compatíveis com a documentação e o schema).

Backends:
  - "xlsx"     : lê a planilha "Bases de dados - Instituto Mondó" e aplica o saneamento reforçado.
  - "postgres" : lê as tabelas do schema `core` (Supabase).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

COLS_FAMILIAS = ["id", "responsavel", "endereco", "numero", "complemento", "endereco_kobo",
                 "comunidade", "bairro", "zona", "loc1", "loc2"]
COLS_MORADORES = ["id", "idm", "nome", "sexo", "nascimento", "idade", "cpf", "telefone",
                  "comunidade", "zona", "bairro", "ciclo", "ipm", "status", "grupo"]
COLS_ATIVIDADES = ["id", "idm", "nome", "comunidade", "dimensao", "atividade_turma", "atividade",
                   "inicio", "fim", "categoria", "tipo", "turma", "doacao", "cesta"]
COLS_AVALIACAO = (["dimensao", "evento", "data_texto", "nome_avaliador", "id_raw",
                   "q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08", "q09",
                   "turno_preferido", "turno_manha", "turno_tarde", "turno_noite", "turno_fim_semana",
                   "intencao",
                   "int_trabalhar_area", "int_primeiro_emprego", "int_mudar_area", "int_crescer_carreira",
                   "int_abrir_negocio", "int_renda_extra", "int_interesse_pessoal", "int_feiras_eventos",
                   "int_indeciso", "int_outro",
                   "outro_texto", "elogios_texto", "melhorias_texto", "nota_geral",
                   "formato", "categoria_elogios", "categoria_melhorias"])
MARCADORES_NULOS = {"", "#N/A", "N/A", "NAN", "NONE", "N/R", "NULL", "-", "?"}
IDM_EXTERNOS = {"FORA", "NAO", "FORA DO PROGRAMA", "NAO ENCONTRADO", "EXTERNO", "SEM ID", "SEM CADASTRO"}

# Linhas da aba "avaliação" cujas respostas ficaram deslocadas 1 coluna para a direita (ver _realinhar_avaliacao).
# O deslocamento começa nesta coluna e vai até a última. CONFIRME olhando as linhas afetadas na planilha
# (ex.: 1223 a 1262): se o valor 0/1 de "Outro" aparece na coluna do texto do "Outro", o ponto de partida é int_outro.
REALINHAR_A_PARTIR_DE = "int_outro"


# ------------------------------------------------------------------ utilitários de texto
def _norm(v) -> str:
    t = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def _nulo(v) -> bool:
    return v is None or (not isinstance(v, str) and pd.isna(v))


def _limpa(s: pd.Series) -> pd.Series:
    """Remove espaços duplicados e converte marcadores (#N/A, n/r, vazio) em nulo."""
    def f(v):
        if _nulo(v):
            return None
        t = re.sub(r"\s+", " ", str(v)).strip()
        return None if t.upper() in MARCADORES_NULOS else t
    return s.astype(object).map(f)


def _limpa_idm(s: pd.Series) -> pd.Series:
    """Normaliza códigos IDM ('84. 1' -> '84.1', '228.1 um' -> '228.1') e anula rótulos genéricos ('Fora', 'Não')."""
    def f(v):
        if _nulo(v):
            return None
        t = re.sub(r"\s+", " ", str(v)).strip()
        if t.upper() in MARCADORES_NULOS or _norm(t) in IDM_EXTERNOS:
            return None
        m = re.match(r"^(\d+)\s*\.\s*(\d+)(?:\s+[a-zA-Z]+)?$", t)
        if m:
            return f"{m.group(1)}.{m.group(2)}"
        return t
    return s.astype(object).map(f)


def _resolver_colisoes_idm(M: pd.DataFrame):
    """O Excel grava o 10º morador de uma família ('5.10') como número, e ele vira '5.1', igual ao 1º.

    Em vez de descartar o repetido, renomeia a 2ª ocorrência de 'X.n' (n de 1 dígito) para 'X.n0'.
    Devolve (moradores, renomeados, descartados). Só descarta se o novo código também já existir.
    """
    usados = set(M["codigo_morador"])
    vistos: set[str] = set()
    novo = M["codigo_morador"].copy()
    renomeados = descartados = 0
    for i, cod in M["codigo_morador"].items():
        if cod not in vistos:
            vistos.add(cod)
            continue
        m = re.fullmatch(r"(\d+)\.(\d)", cod)
        cand = f"{m.group(1)}.{m.group(2)}0" if m else None
        if cand and cand not in usados:
            novo[i] = cand
            usados.add(cand)
            vistos.add(cand)
            renomeados += 1
        else:
            novo[i] = None
            descartados += 1
    M = M.copy()
    M["codigo_morador"] = novo
    return M[M["codigo_morador"].notna()].reset_index(drop=True), renomeados, descartados


def _texto_nao_numerico(v) -> bool:
    if _nulo(v):
        return False
    t = str(v).strip()
    if not t or t.upper() in MARCADORES_NULOS:
        return False
    return pd.isna(pd.to_numeric(t.replace(",", "."), errors="coerce"))


def _realinhar_avaliacao(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Corrige linhas da aba avaliação em que as respostas finais ficaram 1 coluna à direita.

    Sinais: o texto do "Outro" traz 0/1 (era o valor de int_outro) ou a nota geral traz um texto (era a melhoria).
    Correção: das colunas de REALINHAR_A_PARTIR_DE até categoria_melhorias, cada valor volta 1 coluna para a esquerda.
    A nota geral NÃO é recalculada: se o valor que sobrar nela não for um número de 0 a 5, fica vazia.
    Devolve (dados, linhas realinhadas, linhas cuja nota ficou vazia).
    """
    df = df.astype(object)
    out = df.copy()
    cols = COLS_AVALIACAO[COLS_AVALIACAO.index(REALINHAR_A_PARTIR_DE):]
    outro_01 = out["outro_texto"].map(
        lambda v: not _nulo(v) and str(v).strip().replace(",", ".") in {"0", "1", "0.0", "1.0"})
    mask = outro_01 | out["nota_geral"].map(_texto_nao_numerico)
    n_corr = int(mask.sum())
    sem_nota = 0
    if n_corr:
        for i, c in enumerate(cols):
            out.loc[mask, c] = df.loc[mask, cols[i + 1]] if i + 1 < len(cols) else None
        nota = pd.to_numeric(out.loc[mask, "nota_geral"].map(lambda v: None if _nulo(v) else str(v).replace(",", ".")),
                             errors="coerce")
        invalida = ~nota.between(0, 5)
        out.loc[mask[mask].index[invalida.values], "nota_geral"] = None
        sem_nota = int(invalida.sum())
    return out, n_corr, sem_nota


def _mapa_canonico(*series: pd.Series) -> dict:
    """Une variantes de caixa/acento/espaço ('Oftalmologia' e 'OFTALMOLOGIA') na forma mais frequente."""
    valores = pd.concat([_limpa(s) for s in series], ignore_index=True).dropna()
    if valores.empty:
        return {}
    chaves = valores.map(_norm)
    melhor = valores.groupby(chaves).agg(lambda x: x.value_counts().index[0])
    return {v: melhor[_norm(v)] for v in valores.unique()}


def _aplica(s: pd.Series, mapa: dict) -> pd.Series:
    return _limpa(s).map(lambda v: None if _nulo(v) else mapa.get(v, v))


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(_limpa(s).map(lambda v: None if _nulo(v) else v.replace(",", ".")), errors="coerce")


def _bool(s: pd.Series) -> pd.Series:
    n = pd.to_numeric(s, errors="coerce")
    return n.map(lambda v: None if pd.isna(v) else bool(v)).astype("boolean")


def _digitos(v) -> str | None:
    if _nulo(v):
        return None
    t = str(v)
    if re.fullmatch(r"\d+\.0", t):
        t = t[:-2]
    d = re.sub(r"\D", "", t)
    return d or None


def _cpf(v) -> str | None:
    d = _digitos(v)
    if d is None or not (8 <= len(d) <= 11):
        return None
    return d.zfill(11)


def cpf_valido(c) -> bool:
    if c is None or not re.fullmatch(r"\d{11}", str(c)) or len(set(c)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(c[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(c[n]):
            return False
    return True


def _telefone(v) -> str | None:
    d = _digitos(v)
    return d if d and 8 <= len(d) <= 13 else None


def _primeiro(x):
    x = x.dropna()
    return x.iloc[0] if len(x) else None


def _lookup(valores, id_col: str) -> pd.DataFrame:
    nomes = sorted({v for v in valores if not _nulo(v)})
    return pd.DataFrame({id_col: range(1, len(nomes) + 1), "nome": nomes})


# ------------------------------------------------------------------ leitura
def _renomear(df: pd.DataFrame, nomes: list[str], aba: str) -> pd.DataFrame:
    if df.shape[1] < len(nomes):
        raise ValueError(f"A aba '{aba}' tem {df.shape[1]} colunas; esperado ao menos {len(nomes)}. "
                         "A planilha mudou de estrutura?")
    out = df.iloc[:, :len(nomes)].copy()
    out.columns = nomes
    return out


def ler_planilha(caminho: Path) -> dict[str, pd.DataFrame]:
    abas = pd.read_excel(caminho, sheet_name=None, dtype=object)

    def achar(nome):
        for k, df in abas.items():
            if _norm(k) == _norm(nome):
                return df
        raise ValueError(f"Aba '{nome}' não encontrada. Abas disponíveis: {list(abas)}")

    return {"familias": _renomear(achar("Familias"), COLS_FAMILIAS, "Familias"),
            "moradores": _renomear(achar("Moradores"), COLS_MORADORES, "Moradores"),
            "atividades": _renomear(achar("atividades"), COLS_ATIVIDADES, "atividades"),
            "avaliacao": _renomear(achar("avaliação"), COLS_AVALIACAO, "avaliação")}


# ------------------------------------------------------------------ construção do modelo
def construir_modelo(abas: dict[str, pd.DataFrame]):
    """Devolve (frames, qualidade). `frames` segue o dicionário de dados da documentação v0.3."""
    F, M, A, V = (abas[k].copy() for k in ("familias", "moradores", "atividades", "avaliacao"))
    q: list[dict] = []

    def reg(qid, problema, n, base=None):
        q.append({"id": qid, "problema": problema, "ocorrencias": int(n),
                  "base": None if base is None else int(base),
                  "percentual": None if not base else round(100 * n / base, 1)})

    # ---------- lookups
    m_com = _mapa_canonico(F["comunidade"], M["comunidade"], A["comunidade"])
    comunidade = _lookup(m_com.values(), "id_comunidade")
    id_com = dict(zip(comunidade["nome"], comunidade["id_comunidade"]))

    m_dim = _mapa_canonico(A["dimensao"], V["dimensao"])
    dimensao = _lookup(m_dim.values(), "id_dimensao").assign(sigla=None)
    id_dim = dict(zip(dimensao["nome"], dimensao["id_dimensao"]))

    m_cat = _mapa_canonico(A["categoria"])
    categoria = _lookup(m_cat.values(), "id_categoria")
    id_cat = dict(zip(categoria["nome"], categoria["id_categoria"]))

    m_tipo = _mapa_canonico(A["tipo"])
    m_turma = _mapa_canonico(A["turma"])
    m_ativ = _mapa_canonico(A["atividade"])
    itens_brutos = _limpa(A["doacao"]).map(lambda v: None if v is None or _norm(v) == "SIM" else v)
    m_item = _mapa_canonico(itens_brutos)
    item_doacao = _lookup(m_item.values(), "id_item_doacao")
    item_doacao["tipo"] = item_doacao["nome"].map(
        lambda n: "Óculos" if "OCULOS" in _norm(n) else ("Kit" if _norm(n).startswith("KIT") else None))
    id_item = dict(zip(item_doacao["nome"], item_doacao["id_item_doacao"]))

    # ---------- família
    F["id_familia"] = pd.to_numeric(F["id"], errors="coerce")
    F = F.dropna(subset=["id_familia"])
    reg("Q-06a", "Famílias com ID repetido (mantida a primeira)", F.duplicated("id_familia").sum(), len(F))
    F = F.drop_duplicates("id_familia").copy()
    F["id_familia"] = F["id_familia"].astype("int64")
    xy = _limpa(F["loc1"]).str.extract(r"q=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)").astype(float)
    familia = pd.DataFrame({
        "id_familia": F["id_familia"].values,
        "responsavel_nome": _limpa(F["responsavel"]).values,
        "endereco": _limpa(F["endereco"]).values,
        "numero": _limpa(F["numero"]).map(lambda v: None if _nulo(v) else re.sub(r"\.0$", "", v)).values,
        "complemento": _limpa(F["complemento"]).map(lambda v: None if _nulo(v) else re.sub(r"\.0$", "", v)).values,
        "endereco_kobo": _limpa(F["endereco_kobo"]).values,
        "id_comunidade": _aplica(F["comunidade"], m_com).map(id_com).astype("Int64").values,
        "bairro": _limpa(F["bairro"]).values,
        "zona": _limpa(F["zona"]).map(lambda v: None if _nulo(v) else _norm(v)).values,
        "latitude": xy[0].values, "longitude": xy[1].values,
    })
    reg("Q-06b", "Famílias sem localização (coordenadas)", familia["latitude"].isna().sum(), len(familia))

    # ---------- morador
    M["codigo_morador"] = _limpa_idm(M["idm"])
    M["id_familia"] = pd.to_numeric(M["id"], errors="coerce")
    M = M[M["codigo_morador"].notna()].reset_index(drop=True)
    M["codigo_original"] = M["codigo_morador"]
    M["nome_norm"] = M["nome"].map(lambda v: None if _nulo(v) else _norm(v))
    M, n_renom, n_desc = _resolver_colisoes_idm(M)
    reg("Q-05", "Códigos de morador repetidos pelo Excel (X.10 gravado como X.1): 2ª ocorrência renomeada para X.n0",
        n_renom, len(M))
    reg("Q-05b", "Códigos de morador repetidos sem solução automática (descartados; mantido o primeiro)",
        n_desc, len(M) + n_desc)

    # moradores com o mesmo código na planilha: as atividades/avaliações são ligadas pelo NOME
    cod_ambiguos = set(M.loc[M["codigo_original"] != M["codigo_morador"], "codigo_original"])
    por_nome = {(o, n): c for o, n, c in zip(M["codigo_original"], M["nome_norm"], M["codigo_morador"])
                if o in cod_ambiguos and n}

    def desambiguar(idm: pd.Series, nome: pd.Series) -> pd.Series:
        saida = []
        for i, n in zip(idm, nome):
            if not _nulo(i) and i in cod_ambiguos and not _nulo(n):
                saida.append(por_nome.get((i, _norm(n)), i))
            else:
                saida.append(i)
        return pd.Series(saida, index=idm.index, dtype=object)

    cpf_bruto = M["cpf"].map(_digitos)
    cpf = M["cpf"].map(_cpf)
    morador = pd.DataFrame({
        "id_morador": np.arange(1, len(M) + 1),
        "codigo_morador": M["codigo_morador"],
        "id_familia": M["id_familia"].astype("Int64"),
        "nome": _limpa(M["nome"]),
        "sexo": _aplica(M["sexo"], _mapa_canonico(M["sexo"])),
        "data_nascimento": pd.to_datetime(M["nascimento"], errors="coerce"),
        "cpf": cpf,
        "telefone": M["telefone"].map(_telefone),
        "id_comunidade": _aplica(M["comunidade"], m_com).map(id_com).astype("Int64"),
        "bairro": _limpa(M["bairro"]),
        "zona": _limpa(M["zona"]).map(lambda v: None if _nulo(v) else _norm(v)),
        "ciclo": pd.to_numeric(M["ciclo"], errors="coerce").astype("Int64"),
        "ipm": pd.to_numeric(M["ipm"], errors="coerce").astype("Int64"),
        "status": _aplica(M["status"], _mapa_canonico(M["status"])),
        "grupo": pd.to_numeric(M["grupo"], errors="coerce").astype("Int64"),
    })
    sem_fam = ~morador["id_familia"].isin(familia["id_familia"])
    reg("Q-06c", "Moradores cuja família não consta em Familias", sem_fam.sum(), len(morador))
    reg("Q-03a", "CPF não preenchido", morador["cpf"].isna().sum(), len(morador))
    reg("Q-03b", "CPF preenchido com menos de 11 dígitos (zeros à esquerda completados)",
        cpf_bruto.map(lambda d: isinstance(d, str) and len(d) < 11).sum(), morador["cpf"].notna().sum())
    reg("Q-03c", "CPF com dígito verificador inválido", (morador["cpf"].notna() & ~morador["cpf"].map(cpf_valido)).sum(),
        morador["cpf"].notna().sum())
    reg("Q-03d", "CPF repetido entre moradores", morador["cpf"].dropna().duplicated().sum(), morador["cpf"].notna().sum())
    reg("Q-04", "Telefone não preenchido", morador["telefone"].isna().sum(), len(morador))

    # ---------- participantes do cadastro
    cad = pd.DataFrame({"id_participante": morador["id_morador"].values, "id_morador": morador["id_morador"].values,
                        "nome": morador["nome"].values, "origem": "cadastro"})
    cod2part = dict(zip(morador["codigo_morador"], cad["id_participante"]))

    # ---------- atividades
    reg("Q-08", "Linhas de atividades totalmente duplicadas (unificadas)", abas["atividades"].duplicated().sum(), len(A))
    A["idm"] = _limpa_idm(A["idm"])
    A["nome"] = _limpa(A["nome"])
    A["idm"] = desambiguar(A["idm"], A["nome"])
    A["ativ"] = _aplica(A["atividade"], m_ativ)
    A["dim"] = _aplica(A["dimensao"], m_dim)
    A["cat"] = _aplica(A["categoria"], m_cat)
    A["tipo_c"] = _aplica(A["tipo"], m_tipo).fillna("GERAL")
    A["turma_c"] = _aplica(A["turma"], m_turma)
    A["inicio"] = pd.to_datetime(A["inicio"], errors="coerce")
    A["fim"] = pd.to_datetime(A["fim"], errors="coerce")
    invalidas = A["ativ"].isna() | A["inicio"].isna() | A["fim"].isna()
    reg("Q-07d", "Linhas de atividades sem nome da atividade ou sem datas de início/fim (descartadas)",
        invalidas.sum(), len(A))
    A = A[~invalidas].copy()

    reg("Q-07a", "Linhas de atividades só com nome (ou IDM 'Fora'/'Não'): tratadas como participante externo",
        (A["idm"].isna() & A["nome"].notna()).sum(), len(A))
    reg("Q-07b", "Linhas de atividades com IDM numérico inexistente em Moradores: tratadas como participante externo",
        (A["idm"].notna() & ~A["idm"].isin(cod2part)).sum(), A["idm"].notna().sum())

    def chave_externo(idm, nome):
        if not _nulo(idm) and idm in cod2part:
            return None
        if not _nulo(idm):
            return f"idm:{idm}"
        if not _nulo(nome):
            return f"nome:{_norm(nome)}"
        return "sem-id"
    A["chave_ext"] = [chave_externo(i, n) for i, n in zip(A["idm"], A["nome"])]
    reg("Q-07c", "Linhas de atividades sem IDM e sem nome (descartadas)", (A["chave_ext"] == "sem-id").sum(), len(A))
    A = A[A["chave_ext"] != "sem-id"].copy()

    ext = (A[A["chave_ext"].notna()].groupby("chave_ext")["nome"]
           .agg(lambda x: x.value_counts().index[0] if x.notna().any() else None).reset_index())
    ext["id_participante"] = np.arange(len(cad) + 1, len(cad) + len(ext) + 1)
    chave2part = dict(zip(ext["chave_ext"], ext["id_participante"]))
    participante = pd.concat([
        cad,
        pd.DataFrame({"id_participante": ext["id_participante"], "id_morador": pd.NA,
                      "nome": ext["nome"], "origem": "externo"}),
    ], ignore_index=True)
    participante["id_morador"] = participante["id_morador"].astype("Int64")
    A["id_participante"] = [cod2part.get(i) if _nulo(k) else chave2part.get(k)
                            for i, k in zip(A["idm"], A["chave_ext"])]

    # catálogo de atividades
    moda = lambda x: x.value_counts().index[0] if x.notna().any() else None
    cat_ativ = A.groupby("ativ").agg(dim=("dim", moda), cat=("cat", moda),
                                     n_dim=("dim", "nunique"), n_cat=("cat", "nunique")).reset_index()
    reg("Q-11", "Atividades com mais de uma dimensão ou categoria (a classificação de cada oferta é mantida)",
        ((cat_ativ["n_dim"] > 1) | (cat_ativ["n_cat"] > 1)).sum(), len(cat_ativ))
    atividade = pd.DataFrame({
        "id_atividade": np.arange(1, len(cat_ativ) + 1), "nome": cat_ativ["ativ"].values,
        "id_dimensao": cat_ativ["dim"].map(id_dim).values, "id_categoria": cat_ativ["cat"].map(id_cat).values})
    id_ativ = dict(zip(atividade["nome"], atividade["id_atividade"]))

    # ofertas (com dimensão e categoria específicas da oferta)
    A["turma_key"] = A["turma_c"].fillna("")
    of = (A.groupby(["ativ", "turma_key", "inicio", "fim"], as_index=False)
           .agg(dim=("dim", moda), cat=("cat", moda), n_dim=("dim", "nunique"), n_cat=("cat", "nunique")))
    reg("Q-11b", "Ofertas (mesma atividade, turma e datas) com mais de uma dimensão/categoria: vale a mais frequente",
        ((of["n_dim"] > 1) | (of["n_cat"] > 1)).sum(), len(of))
    of["id_oferta"] = np.arange(1, len(of) + 1)
    A = A.merge(of[["ativ", "turma_key", "inicio", "fim", "id_oferta"]],
                on=["ativ", "turma_key", "inicio", "fim"], how="left")
    oferta = pd.DataFrame({
        "id_oferta": of["id_oferta"],
        "id_atividade": of["ativ"].map(id_ativ),
        "id_dimensao": of["dim"].map(id_dim).astype("Int64"),
        "id_categoria": of["cat"].map(id_cat).astype("Int64"),
        "turma": of["turma_key"].replace("", None),
        "data_inicio": of["inicio"],
        "data_fim": of["fim"],
        "id_projeto": pd.array([pd.NA] * len(of), dtype="Int64"),
        "id_formador": pd.array([pd.NA] * len(of), dtype="Int64"),
        "id_rubrica": pd.array([pd.NA] * len(of), dtype="Int64"),
        "id_indicador": pd.array([pd.NA] * len(of), dtype="Int64"),
        "local": None, "descricao": None, "foto_coletiva": None, "link_documentacao": None})
    reg("Q-09", "Ofertas com data final anterior à inicial", (oferta["data_fim"] < oferta["data_inicio"]).sum(), len(oferta))

    # participações
    A["item"] = _aplica(A["doacao"].map(lambda v: None if _nulo(v) or _norm(v) == "SIM" else v), m_item)
    A["tem_doacao"] = A["doacao"].map(lambda v: not _nulo(v) and str(v).strip() != "")
    A["tem_cesta"] = A["cesta"].map(lambda v: not _nulo(v) and _norm(v) == "SIM")
    A["com_c"] = _aplica(A["comunidade"], m_com)
    bruto = len(A)
    pc = (A.groupby(["id_oferta", "id_participante", "tipo_c"], as_index=False)
            .agg(doacao=("tem_doacao", "max"), cesta_basica=("tem_cesta", "max"),
                 item=("item", _primeiro), com=("com_c", _primeiro)))
    reg("Q-08b", "Participações repetidas (mesma oferta, participante e tipo) unificadas", bruto - len(pc), bruto)
    participacao = pd.DataFrame({
        "id_participacao": np.arange(1, len(pc) + 1),
        "id_oferta": pc["id_oferta"], "id_participante": pc["id_participante"], "tipo": pc["tipo_c"],
        "doacao": pc["doacao"].astype(bool), "id_item_doacao": pc["item"].map(id_item).astype("Int64"),
        "cesta_basica": pc["cesta_basica"].astype(bool), "id_comunidade": pc["com"].map(id_com).astype("Int64")})

    # ---------- avaliação
    V, n_desloc, n_sem_nota = _realinhar_avaliacao(V)
    reg("Q-12e", "Avaliações com respostas deslocadas na planilha (realinhadas automaticamente)", n_desloc, len(V))
    reg("Q-12f", "Avaliações realinhadas cuja nota geral ficou vazia (valor não numérico de 0 a 5)", n_sem_nota,
        n_desloc or None)
    V["idm"] = _limpa_idm(V["id_raw"])
    V["idm"] = desambiguar(V["idm"], _limpa(V["nome_avaliador"]))
    reg("Q-12a", "Avaliações sem ID de morador", V["idm"].isna().sum(), len(V))
    reg("Q-12b", "Avaliações com ID que não existe em Moradores", (V["idm"].notna() & ~V["idm"].isin(cod2part)).sum(),
        V["idm"].notna().sum())
    datas = V["data_texto"].map(lambda v: pd.Timestamp(v) if hasattr(v, "year") else
                                (pd.to_datetime(v, format="%d/%m/%Y", errors="coerce") if isinstance(v, str) else pd.NaT))
    texto = V["data_texto"].map(lambda v: None if _nulo(v) or hasattr(v, "year") else str(v).strip())
    reg("Q-12c", "Avaliações sem data da formação interpretável", datas.isna().sum(), len(V))
    reg("Q-12d", "Pergunta 09 (lanche) sem resposta preenchida", V["q09"].isna().sum(), len(V))
    avaliacao = pd.DataFrame({
        "id_avaliacao": np.arange(1, len(V) + 1), "id_oferta": pd.array([pd.NA] * len(V), dtype="Int64"),
        "id_participante": V["idm"].map(cod2part).astype("Int64"),
        "id_dimensao": _aplica(V["dimensao"], m_dim).map(id_dim).astype("Int64"),
        "evento": _limpa(V["evento"]), "data_formacao": datas, "data_formacao_texto": texto,
        "nome_avaliador": _limpa(V["nome_avaliador"]),
    })
    for c in ["q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08", "q09"]:
        n = {"q01": "q01_aprendizado", "q02": "q02_organizacao", "q03": "q03_professores", "q04": "q04_recomendacao",
             "q05": "q05_infraestrutura", "q06": "q06_duracao", "q07": "q07_informacoes_previas",
             "q08": "q08_material", "q09": "q09_lanche"}[c]
        avaliacao[n] = _num(V[c]).astype("Int64")
    avaliacao["turno_preferido"] = _limpa(V["turno_preferido"])
    for c in ["turno_manha", "turno_tarde", "turno_noite", "turno_fim_semana"]:
        avaliacao[c] = _bool(V[c])
    avaliacao["intencao"] = _limpa(V["intencao"])
    for c in [c for c in COLS_AVALIACAO if c.startswith("int_")]:
        avaliacao[c] = _bool(V[c])
    avaliacao["outro_texto"] = _limpa(V["outro_texto"])
    avaliacao["elogios_texto"] = _limpa(V["elogios_texto"])
    avaliacao["melhorias_texto"] = _limpa(V["melhorias_texto"])
    avaliacao["nota_geral"] = _num(V["nota_geral"])
    avaliacao["formato"] = _aplica(V["formato"], _mapa_canonico(V["formato"]))
    avaliacao["categoria_elogios"] = _limpa(V["categoria_elogios"])
    avaliacao["categoria_melhorias"] = _limpa(V["categoria_melhorias"])

    frames = {"dimensao": dimensao, "categoria_atividade": categoria, "comunidade": comunidade,
              "item_doacao": item_doacao, "atividade": atividade, "oferta": oferta,
              "participacao": participacao, "participante": participante, "morador": morador,
              "familia": familia, "avaliacao": avaliacao}
    return frames, pd.DataFrame(q)


# ------------------------------------------------------------------ backends
TABELAS_CORE = ["dimensao", "categoria_atividade", "comunidade", "item_doacao", "atividade", "oferta",
                "participacao", "participante", "morador", "familia", "avaliacao"]
_INTEIROS = {
    "oferta": ["id_dimensao", "id_categoria", "id_projeto", "id_formador", "id_rubrica", "id_indicador"],
    "familia": ["id_comunidade"],
    "morador": ["id_familia", "id_comunidade", "ciclo", "ipm", "grupo"],
    "participante": ["id_morador"],
    "participacao": ["id_item_doacao", "id_comunidade"],
    "atividade": ["id_dimensao", "id_categoria"],
    "avaliacao": ["id_oferta", "id_participante", "id_dimensao", "q01_aprendizado", "q02_organizacao",
                  "q03_professores", "q04_recomendacao", "q05_infraestrutura", "q06_duracao",
                  "q07_informacoes_previas", "q08_material", "q09_lanche"],
}
_DATAS = {"oferta": ["data_inicio", "data_fim"], "morador": ["data_nascimento"], "avaliacao": ["data_formacao"]}
_NUMEROS = {"familia": ["latitude", "longitude"], "avaliacao": ["nota_geral"]}
_BOOLEANOS = {"avaliacao": ["turno_manha", "turno_tarde", "turno_noite", "turno_fim_semana", "int_trabalhar_area",
                            "int_primeiro_emprego", "int_mudar_area", "int_crescer_carreira", "int_abrir_negocio",
                            "int_renda_extra", "int_interesse_pessoal", "int_feiras_eventos", "int_indeciso",
                            "int_outro"]}


def _tipar(tabela: str, df: pd.DataFrame) -> pd.DataFrame:
    for c in _INTEIROS.get(tabela, []):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in _DATAS.get(tabela, []):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in _NUMEROS.get(tabela, []):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in _BOOLEANOS.get(tabela, []):
        if c in df.columns:
            df[c] = df[c].astype("boolean")
    return df


# ------------------------------------------------------------------ padronização de maiúsculas/minúsculas
# Regra: textos TODOS EM MAIÚSCULAS viram "Frase" (ou "Nome Próprio", se forem lugares). Em algumas colunas
# (PADRONIZAR, terceira lista) o formato "Frase" é aplicado sempre. Abreviações com pontos (D.E., S.A.) são mantidas.
SIGLAS = {"IPM", "EJA", "UBS", "CRAS", "CREAS", "SUS", "ONG", "APS", "CPF", "LGPD", "TEA", "TDAH", "PCD", "IBGE"}
NOMES_PROPRIOS = {"marajó": "Marajó", "pará": "Pará", "breves": "Breves", "portel": "Portel", "afuá": "Afuá",
                  "mondó": "Mondó", "amazônia": "Amazônia", "brasil": "Brasil"}
PALAVRAS_PEQUENAS = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos", "a", "o", "para", "com"}


def _so_maiusculas(t: str) -> bool:
    letras = [c for c in t if c.isalpha()]
    return len(letras) >= 3 and all(c.isupper() for c in letras)


def padroniza_texto(t, lugar: bool = False, sempre: bool = False):
    if not isinstance(t, str) or not (sempre or _so_maiusculas(t)):
        return t
    saida, primeira = [], True
    for w in re.split(r"(\s+)", t):
        if not w.strip():
            saida.append(w)
            continue
        pre, nu, suf = re.match(r"^(\W*)(.*?)(\W*)$", w, flags=re.S).groups()
        if re.search(r"[^\W\d_]\.[^\W\d_]", nu):        # abreviação com pontos (D.E.): não mexe
            primeira = False
            saida.append(w)
            continue
        nu = nu.lower()
        if nu.upper() in SIGLAS:
            nu = nu.upper()
        elif nu in NOMES_PROPRIOS:
            nu = NOMES_PROPRIOS[nu]
        elif lugar and nu not in PALAVRAS_PEQUENAS:
            nu = nu[:1].upper() + nu[1:]
        if primeira and nu:
            nu, primeira = nu[:1].upper() + nu[1:], False
        saida.append(pre + nu + suf)
    return "".join(saida)


PADRONIZAR = {
    "dimensao": ([], [], ["nome"]), "categoria_atividade": ([], [], ["nome"]), "item_doacao": ([], [], ["nome"]),
    "atividade": (["nome"], [], []), "comunidade": ([], ["nome"], []), "participacao": ([], [], ["tipo"]),
    "familia": (["zona"], ["bairro"], []), "morador": (["sexo", "status", "zona"], ["bairro"], []),
    "avaliacao": (["evento", "formato", "categoria_elogios", "categoria_melhorias"], [], []),
}


def padronizar_frames(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out = dict(frames)
    for tabela, (so_caps, lugar, sempre) in PADRONIZAR.items():
        if tabela not in out:
            continue
        df = out[tabela].copy()
        for cols, kw in ((so_caps, {}), (lugar, {"lugar": True}), (sempre, {"sempre": True})):
            for col in cols:
                if col in df.columns:
                    df[col] = df[col].map(lambda v, kw=kw: padroniza_texto(v, **kw)).astype(df[col].dtype)
        out[tabela] = df
    return out


def carregar_postgres(url: str):
    from sqlalchemy import create_engine, text
    eng = create_engine(url, pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            frames = {t: _tipar(t, pd.read_sql(text(f"select * from core.{t}"), conn)) for t in TABELAS_CORE}
            quali = pd.read_sql(text("select id, problema, ocorrencias, base, percentual from core.carga_qualidade "
                                     "order by id"), conn)
            quali["percentual"] = pd.to_numeric(quali["percentual"], errors="coerce").astype("float64")
            quali["ocorrencias"] = quali["ocorrencias"].astype(int)
            meta = pd.read_sql(text("select carregado_em, origem, mascarado from core.carga_info where id = 1"), conn)
    finally:
        eng.dispose()
    if meta.empty:
        info = {"mascarado": False, "origem": "desconhecida", "carregado_em": None}
    else:
        info = {"mascarado": bool(meta.loc[0, "mascarado"]), "origem": meta.loc[0, "origem"],
                "carregado_em": str(meta.loc[0, "carregado_em"])}
    return frames, quali, info


def carregar(settings):
    """Devolve (frames, qualidade, info) conforme o backend configurado, com os textos padronizados."""
    frames, quali, info = _carregar_bruto(settings)
    return padronizar_frames(frames), quali, info


def _carregar_bruto(settings):
    if settings.backend == "postgres":
        if not settings.postgres_url:
            raise ValueError("Defina data.postgres_url em .streamlit/secrets.toml.")
        return carregar_postgres(settings.postgres_url)
    if not settings.xlsx_path or not Path(settings.xlsx_path).exists():
        from .config import ROOT
        pasta = ROOT / "data"
        achados = sorted(p.name for p in pasta.iterdir()) if pasta.exists() else []
        raise FileNotFoundError(
            "Planilha não encontrada. "
            + (f"Caminho configurado: {settings.xlsx_path}. " if settings.xlsx_path else "")
            + f"Pasta procurada: {pasta} (arquivos nela: {achados or 'nenhum'}). "
            "Coloque um arquivo .xlsx nessa pasta ou defina data.xlsx_path em .streamlit/secrets.toml.")
    caminho = Path(settings.xlsx_path)
    frames, quali = construir_modelo(ler_planilha(caminho))
    return frames, quali, {"mascarado": caminho.resolve().parent.name == "demo", "origem": caminho.name,
                           "carregado_em": None}
