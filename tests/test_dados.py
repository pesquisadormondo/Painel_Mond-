import io
from datetime import date

import pandas as pd

from mondo import dados as dd
from mondo.metrics import avaliacao_enriquecida, fato_participacao, morador_enriquecido
from mondo.privacy import para_pesquisa
from tests.fixtures import NOMES_FICTICIOS

REF = date(2026, 11, 4)


def _pseudo(modelo):
    fp = para_pesquisa(modelo[0], "segredo", REF)
    mor = morador_enriquecido(fp, REF)
    return fp, mor, fato_participacao(fp, mor), avaliacao_enriquecida(fp)


def test_agregar_e_supressao_publica(modelo):
    fp, mor, fato, av = _pseudo(modelo)
    tab = dd.agregar(fato, "participacoes", ["atividade"], ["participacoes", "participantes", "ofertas"])
    pub = dd.suprimir_publico(tab, "participacoes", ["participacoes", "participantes", "ofertas"], 5)
    horta = pub[pub["atividade"] == "HORTA COMUNITÁRIA"].iloc[0]  # oferta pequena do fixture (< 5 pessoas)
    assert horta["participacoes"] == "<5" and horta["participantes"] == "<5"
    sem = dd.suprimir_publico(tab, "participacoes", ["participacoes", "participantes", "ofertas"], 1)
    assert not any(str(v).startswith("<") for v in sem[["participacoes", "participantes"]].to_numpy().ravel())
    fin = dd.finalizar(pub, "participacoes", ["atividade"], ["participacoes", "participantes", "ofertas"])
    assert "__n" not in fin.columns and "Participantes únicos" in fin.columns


def test_total_sem_agrupar_e_medias_suprimidas(modelo):
    fp, mor, fato, av = _pseudo(modelo)
    total = dd.agregar(fato, "participacoes", [], ["participacoes"])
    assert len(total) == 1 and total.loc[0, "participacoes"] == len(fato)
    a = dd.agregar(av.head(3), "avaliacoes", ["dimensao"], ["respostas", "nota_media"])
    s = dd.suprimir_publico(a, "avaliacoes", ["respostas", "nota_media"], 5)
    assert (s["nota_media"] == "<5").all()  # menos de 5 respostas: média também é escondida


def test_agrupar_por_mes_ano_e_booleano(modelo):
    fp, mor, fato, av = _pseudo(modelo)
    t = dd.agregar(fato, "participacoes", ["mes", "ano", "doacao"], ["participacoes"])
    assert set(t["doacao"]) <= {"Sim", "Não"} and t["mes"].str.match(r"\d{4}-\d{2}").all()
    assert t["ano"].map(str).str.fullmatch(r"\d{4}").all()


def test_microdados_sem_identificadores_e_com_k(modelo):
    fp, mor, fato, av = _pseudo(modelo)
    mor_k, part_k, av_k, rel = dd.preparar_microdados(mor, fato, av, fp["participante"], 5)
    assert rel["k"] == 5
    for nome, df in {"moradores": mor_k, "participacoes": part_k, "avaliacoes": av_k}.items():
        csv, _, _ = dd.exportar(df, dd.FORMATOS[0])
        texto = csv.decode("utf-8")
        assert not any(n in texto for n in NOMES_FICTICIOS), nome
    assert {"nome", "cpf", "telefone"}.isdisjoint(mor_k.columns)
    # filtros demográficos usam valores generalizados: nenhuma comunidade rara escapa
    conhecidos = mor_k[mor_k[["comunidade", "faixa_etaria", "sexo", "zona"]].notna().any(axis=1)]
    assert conhecidos.groupby(["comunidade", "faixa_etaria", "sexo", "zona"], dropna=False).size().min() >= 5


def test_formatos_de_exportacao():
    df = pd.DataFrame({"a": [1.5, 2.0], "b": ["ç", "x"], "d": pd.to_datetime(["2025-01-02", "2025-02-03"])})
    csv, mime, ext = dd.exportar(df, dd.FORMATOS[0])
    assert ext == "csv" and b"2025-01-02" in csv and b"1.5" in csv
    csv2, _, _ = dd.exportar(df, dd.FORMATOS[1])
    assert csv2.startswith(b"\xef\xbb\xbf") and b"1,5" in csv2 and b";" in csv2  # BOM + vírgula decimal
    x, mime, ext = dd.exportar(df, dd.FORMATOS[2])
    assert ext == "xlsx" and pd.read_excel(io.BytesIO(x)).shape == (2, 3)


def test_mascarar():
    df = pd.DataFrame({"cpf": ["52998224725", None], "telefone": ["91988887777", None]})
    m = dd.mascarar(df)
    assert m.loc[0, "cpf"] == "***.982.247-**" and m.loc[0, "telefone"].endswith("7777") and m["cpf"].isna().iloc[1]
