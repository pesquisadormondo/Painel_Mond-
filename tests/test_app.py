import os
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.fixtures import NOMES_FICTICIOS

ROOT = Path(__file__).resolve().parents[1]
NIVEIS = ["publico", "pesquisador", "admin"]
PAGINAS_PUBLICAS = ["visao_geral", "atividades", "territorio", "perfil", "saude", "doacoes", "avaliacoes",
                    "indicadores", "sobre"]
SCRIPT = """
import sys
sys.path.insert(0, {root!r})
from tests.ctx_helper import construir_ctx
from mondo import pages
ctx = construir_ctx({nivel!r}, {xlsx!r}, {log!r})
pages.{pagina}(ctx)
"""


def rodar(pagina, nivel, planilha, tmp_path, antes=None):
    at = AppTest.from_string(SCRIPT.format(root=str(ROOT), nivel=nivel, xlsx=str(planilha), pagina=pagina,
                                           log=str(tmp_path / "log.csv")), default_timeout=60)
    if antes:
        antes(at)
    return at.run()


def textos(at):
    partes = []
    for tipo in ("markdown", "caption", "metric", "info", "warning", "error", "subheader", "title"):
        for el in at.get(tipo):
            partes.append(str(getattr(el, "value", "")))
    for df in at.dataframe:
        partes.append(df.value.to_csv(index=False))
    return "\n".join(partes)


@pytest.mark.parametrize("nivel", NIVEIS)
@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_paginas_abrem_sem_erro(pagina, nivel, planilha, tmp_path):
    at = rodar(pagina, nivel, planilha, tmp_path)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("nivel", ["publico", "pesquisador"])
@pytest.mark.parametrize("pagina", PAGINAS_PUBLICAS)
def test_niveis_1_e_2_nao_mostram_identificadores(pagina, nivel, planilha, tmp_path, modelo):
    at = rodar(pagina, nivel, planilha, tmp_path)
    t = textos(at)
    assert not any(n in t for n in NOMES_FICTICIOS)
    assert "Responsavel Ficticio" not in t and "Rua Inventada" not in t
    for cpf in modelo[0]["morador"]["cpf"].dropna():
        assert cpf not in t


def test_publico_suprime_celulas_pequenas(planilha, tmp_path):
    at = rodar("atividades", "publico", planilha, tmp_path)
    assert any("omitidos" in str(c.value) for c in at.caption)  # horta (3 pessoas) < k=5
    tabela = [d.value for d in at.dataframe][-1]
    assert "<5" in tabela.astype(str).to_numpy()


def test_pesquisador_nao_ve_mapa_nem_suprime(planilha, tmp_path):
    at = rodar("territorio", "pesquisador", planilha, tmp_path)
    assert not any("Mapa" in t.label for t in at.tabs)
    at = rodar("territorio", "admin", planilha, tmp_path)
    assert any("Mapa" in t.label for t in at.tabs)


def test_download_exige_aceite_do_termo(planilha, tmp_path):
    at = rodar("dados_pesquisa", "pesquisador", planilha, tmp_path)
    assert not at.exception and len(at.button) == 0  # sem aceite, nenhum botão de gerar
    at.checkbox(key="termo_ok").check().run()
    assert any(b.label == "Gerar pacote de dados" for b in at.button)
    next(b for b in at.button if b.label == "Gerar pacote de dados").click().run()
    assert not at.exception and "pacote" in at.session_state
    log = pd.read_csv(tmp_path / "log.csv")
    assert (log["acao"] == "gerar_pacote").any() and "Pessoa" not in log.to_csv()


@pytest.mark.parametrize("pagina", ["qualidade", "cadastro", "acessos"])
def test_paginas_de_admin(pagina, planilha, tmp_path):
    at = rodar(pagina, "admin", planilha, tmp_path)
    assert not at.exception, [e.value for e in at.exception]


def test_cadastro_busca_registra_sem_texto(planilha, tmp_path):
    def digitar(at):
        pass
    at = rodar("cadastro", "admin", planilha, tmp_path)
    at.text_input[0].set_value("Pessoa Ficticia 2.1").run()
    assert not at.exception and len(at.dataframe) == 1
    log = (tmp_path / "log.csv").read_text(encoding="utf-8")
    assert "consulta_cadastro" in log and "Pessoa Ficticia" not in log


def test_app_completo_em_modo_dev(planilha, monkeypatch, tmp_path):
    monkeypatch.setenv("MONDO_DEV", "1")
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.secrets["data"] = {"xlsx_path": str(planilha)}
    at.secrets["privacy"] = {"pseudo_secret": "segredo-de-teste", "k_min": 5}
    at.secrets["audit"] = {"path": str(tmp_path / "log.csv")}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    for nivel in ("pesquisador", "admin"):
        at.sidebar.radio(key="dev_nivel").set_value(nivel).run()
        assert not at.exception, [e.value for e in at.exception]
