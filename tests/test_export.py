import io
import zipfile
from datetime import date

import pandas as pd

from mondo.exportacao import montar_pacote
from mondo.privacy import para_pesquisa
from tests.fixtures import NOMES_FICTICIOS

REF = date(2026, 11, 4)


def test_pacote_nao_vaza_identificadores(modelo):
    f, _ = modelo
    fp = para_pesquisa(f, "segredo", REF)
    zbytes, resumo, rel = montar_pacote(fp, REF, 5, "teste@local")
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    assert set(z.namelist()) == {"moradores_pseudonimizados.csv", "participacoes_pseudonimizadas.csv",
                                 "avaliacoes_pseudonimizadas.csv", "dicionario_de_dados.csv", "LEIA-ME.txt"}
    texto = "\n".join(z.read(n).decode("utf-8") for n in z.namelist())
    assert not any(n in texto for n in NOMES_FICTICIOS)
    assert "Responsavel Ficticio" not in texto and "Rua Inventada" not in texto and "Texto livre" not in texto
    for cpf in f["morador"]["cpf"].dropna():
        assert cpf not in texto
    mor = pd.read_csv(io.BytesIO(z.read("moradores_pseudonimizados.csv")))
    assert {"nome", "cpf", "telefone", "data_nascimento"}.isdisjoint(mor.columns)
    assert rel["menor_grupo_depois"] >= 5 or rel["menor_grupo_depois"] == 0


def test_para_pesquisa_exige_segredo(modelo):
    import pytest
    with pytest.raises(ValueError):
        para_pesquisa(modelo[0], "", REF)
