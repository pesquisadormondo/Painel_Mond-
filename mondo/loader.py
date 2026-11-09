"""Carrega os dados e devolve o modelo v0.2 (tabelas e colunas iguais às da documentação).

Backends:
  - "xlsx"     : lê a planilha "Bases de dados - Instituto Mondó" e aplica o saneamento da seção 9.
  - "postgres" : lê as tabelas do schema `core` (Supabase). EXPERIMENTAL: depende do script SQL v0.2
                 (próxima etapa) e ainda não foi testado contra um banco real.
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
MARCADORES_NULOS = {"", "#N/A", "N/A", "NAN", "NONE", "N/R", "NULL", "-"}


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
    """Devolve (frames, qualidade). `frames` segue o dicionário de dados da documentação v0.2."""
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
    M["codigo_morador"] = _limpa(M["idm"])
    M["id_familia"] = pd.to_numeric(M["id"], errors="coerce")
    M = M[M["codigo_morador"].notna()]
    dup = M.duplicated("codigo_morador", keep="first")
    reg("Q-05", "Moradores com código (IDM) repetido (mantido o primeiro)", dup.sum(), len(M))
    M = M[~dup].reset_index(drop=True)
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
    cod2mor = dict(zip(morador["codigo_morador"], morador["id_morador"]))
    cad = pd.DataFrame({"id_participante": morador["id_morador"].values, "id_morador": morador["id_morador"].values,
                        "nome": morador["nome"].values, "origem": "cadastro"})
    cod2part = dict(zip(morador["codigo_morador"], cad["id_participante"]))

    # ---------- atividades
    reg("Q-08", "Linhas de atividades totalmente duplicadas (removidas)", abas["atividades"].duplicated().sum(), len(A))
    A["idm"] = _limpa(A["idm"])
    A["nome"] = _limpa(A["nome"])
    A["ativ"] = _aplica(A["atividade"], m_ativ)
    A["dim"] = _aplica(A["dimensao"], m_dim)
    A["cat"] = _aplica(A["categoria"], m_cat)
    A["tipo_c"] = _aplica(A["tipo"], m_tipo).fillna("GERAL")
    A["turma_c"] = _aplica(A["turma"], m_turma)
    A["inicio"] = pd.to_datetime(A["inicio"], errors="coerce")
    A["fim"] = pd.to_datetime(A["fim"], errors="coerce")
    A = A.dropna(subset=["ativ", "inicio", "fim"]).copy()

    reg("Q-07a", "Linhas de atividades só com nome (sem IDM): tratadas como participante externo",
        (A["idm"].isna() & A["nome"].notna()).sum(), len(A))
    reg("Q-07b", "Linhas de atividades com IDM inexistente em Moradores: tratadas como participante externo",
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
    reg("Q-11", "Atividades com mais de uma dimensão ou categoria (usada a mais frequente)",
        ((cat_ativ["n_dim"] > 1) | (cat_ativ["n_cat"] > 1)).sum(), len(cat_ativ))
    atividade = pd.DataFrame({
        "id_atividade": np.arange(1, len(cat_ativ) + 1), "nome": cat_ativ["ativ"].values,
        "id_dimensao": cat_ativ["dim"].map(id_dim).values, "id_categoria": cat_ativ["cat"].map(id_cat).values})
    id_ativ = dict(zip(atividade["nome"], atividade["id_atividade"]))

    # ofertas
    A["turma_key"] = A["turma_c"].fillna("")
    of = A[["ativ", "turma_key", "inicio", "fim"]].drop_duplicates().reset_index(drop=True)
    of["id_oferta"] = np.arange(1, len(of) + 1)
    A = A.merge(of, on=["ativ", "turma_key", "inicio", "fim"], how="left")
    oferta = pd.DataFrame({
        "id_oferta": of["id_oferta"], "id_atividade": of["ativ"].map(id_ativ),
        "turma": of["turma_key"].replace("", None), "data_inicio": of["inicio"], "data_fim": of["fim"],
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
    reg("Q-12a", "Avaliações sem ID de morador", _limpa(V["id_raw"]).isna().sum(), len(V))
    V["idm"] = _limpa(V["id_raw"])
    reg("Q-12b", "Avaliações com ID que não existe em Moradores", (V["idm"].notna() & ~V["idm"].isin(cod2part)).sum(),
        V["idm"].notna().sum())
    datas = V["data_texto"].map(lambda v: pd.Timestamp(v) if hasattr(v, "year") else
                                (pd.to_datetime(v, format="%d/%m/%Y", errors="coerce") if isinstance(v, str) else pd.NaT))
    texto = V["data_texto"].map(lambda v: None if _nulo(v) or hasattr(v, "year") else str(v).strip())
    reg("Q-12c", "Avaliações sem data da formação interpretável", datas.isna().sum(), len(V))
    reg("Q-12d", "Pergunta 09 (lanche) sem nenhuma resposta (não migrada)", int(V["q09"].isna().all()) * len(V), len(V))
    avaliacao = pd.DataFrame({
        "id_avaliacao": np.arange(1, len(V) + 1), "id_oferta": pd.array([pd.NA] * len(V), dtype="Int64"),
        "id_participante": V["idm"].map(cod2part).astype("Int64"),
        "id_dimensao": _aplica(V["dimensao"], m_dim).map(id_dim).astype("Int64"),
        "evento": _limpa(V["evento"]), "data_formacao": datas, "data_formacao_texto": texto,
        "nome_avaliador": _limpa(V["nome_avaliador"]),
    })
    for c in ["q01", "q02", "q03", "q04", "q05", "q06", "q07", "q08"]:
        n = {"q01": "q01_aprendizado", "q02": "q02_organizacao", "q03": "q03_professores", "q04": "q04_recomendacao",
             "q05": "q05_infraestrutura", "q06": "q06_duracao", "q07": "q07_informacoes_previas", "q08": "q08_material"}[c]
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


def carregar_postgres(url: str):
    """EXPERIMENTAL: lê o schema `core` do Supabase/PostgreSQL (nomes de tabelas da documentação v0.2)."""
    from sqlalchemy import create_engine  # import tardio: só necessário neste backend
    eng = create_engine(url)
    frames = {t: pd.read_sql_table(t, eng, schema="core") for t in TABELAS_CORE}
    return frames, pd.DataFrame(columns=["id", "problema", "ocorrencias", "base", "percentual"])


def carregar(settings):
    if settings.backend == "postgres":
        if not settings.postgres_url:
            raise ValueError("Defina data.postgres_url em .streamlit/secrets.toml.")
        return carregar_postgres(settings.postgres_url)
    if not settings.xlsx_path or not Path(settings.xlsx_path).exists():
        raise FileNotFoundError("Planilha não encontrada. Coloque o arquivo .xlsx na pasta data/ "
                                "ou defina data.xlsx_path em .streamlit/secrets.toml.")
    return construir_modelo(ler_planilha(Path(settings.xlsx_path)))
