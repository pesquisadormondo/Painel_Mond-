import pandas as pd

from tests.fixtures import NOMES_FICTICIOS


def test_estrutura_do_modelo(modelo):
    f, q = modelo
    esperadas = {"dimensao", "categoria_atividade", "comunidade", "item_doacao", "atividade", "oferta",
                 "participacao", "participante", "morador", "familia", "avaliacao"}
    assert set(f) == esperadas
    assert f["morador"]["codigo_morador"].is_unique and f["morador"]["id_morador"].is_unique
    assert len(f["oferta"]) == 4 and len(f["atividade"]) == 4  # 3 tipos do mutirão = 1 oferta


def test_cpf_zeros_e_marcadores(modelo):
    m = modelo[0]["morador"]
    cpfs = m["cpf"].dropna()
    assert (cpfs.str.len() == 11).all()
    assert m["cpf"].isna().any()  # '#N/A' virou nulo


def test_normalizacao_de_texto_e_duplicatas(modelo):
    f, q = modelo
    tipos = set(f["participacao"]["tipo"])
    assert not ({"Oftalmologia", "OFTALMOLOGIA"} <= tipos)  # variantes unificadas
    assert f["participacao"].duplicated(["id_oferta", "id_participante", "tipo"]).sum() == 0
    assert q.loc[q["id"] == "Q-08", "ocorrencias"].iloc[0] >= 1
    assert q.loc[q["id"] == "Q-05", "ocorrencias"].iloc[0] == 1


def test_participantes_externos_e_orfaos(modelo):
    p = modelo[0]["participante"]
    assert {"cadastro", "externo"} <= set(p["origem"])
    ext = p[p["origem"] == "externo"]
    assert ext["id_morador"].isna().all() and len(ext) >= 2
    assert modelo[0]["participacao"]["id_participante"].notna().all()


def test_avaliacao_tipos(modelo):
    av = modelo[0]["avaliacao"]
    assert pd.api.types.is_numeric_dtype(av["nota_geral"]) and av["nota_geral"].between(4, 5).all()
    assert av["outro_texto"].isna().all()  # 'n/r' virou nulo
    assert str(av["turno_tarde"].dtype) == "boolean"


def test_nomes_do_cadastro_nao_inventados(modelo):
    assert set(modelo[0]["morador"]["nome"]) <= set(NOMES_FICTICIOS)
