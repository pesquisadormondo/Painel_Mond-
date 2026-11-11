import os
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from tests.fixtures import NOMES_FICTICIOS

ROOT = Path(__file__).resolve().parents[1]
NIVEIS = ["publico", "pesquisador", "admin"]
PAGINAS_PUBLICAS = ["visao_geral", "atividades", "territorio", "perfil", "saude", "doacoes", "avaliacoes",
                    "indicadores", "dados", "sobre"]
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


def _escolher(at, tabela):
    at.selectbox(key="dl_tabela").set_value(tabela).run()
    return at


def test_pesquisador_microdados_exigem_termo(planilha, tmp_path):
    def antes(at):
        pass
    at = rodar("dados", "pesquisador", planilha, tmp_path)
    _escolher(at, "Participações — microdados pseudonimizados")
    assert not at.exception
    assert any("termo" in w.value.lower() for w in at.warning) and len(at.dataframe) == 0
    at.checkbox(key="termo_ok").check().run()
    assert not at.exception and len(at.dataframe) == 1 and len(at.dataframe[0].value) > 0


def test_pesquisador_pacote_zip_e_log(planilha, tmp_path):
    at = rodar("dados", "pesquisador", planilha, tmp_path)
    _escolher(at, "Pacote completo (.zip)")
    at.checkbox(key="termo_ok").check().run()
    next(b for b in at.button if b.label == "Gerar pacote de dados").click().run()
    assert not at.exception and "pacote" in at.session_state
    log = pd.read_csv(tmp_path / "log.csv")
    assert (log["acao"] == "gerar_pacote").any() and "Pessoa" not in log.to_csv()


def test_admin_gera_pacote_pseudonimizado(planilha, tmp_path):
    at = rodar("dados", "admin", planilha, tmp_path)
    _escolher(at, "Pacote completo (.zip)")
    next(b for b in at.button if b.label == "Gerar pacote de dados").click().run()
    assert not at.exception and "pacote" in at.session_state


def test_admin_tabela_identificada_mascara_cpf(planilha, tmp_path, modelo):
    at = rodar("dados", "admin", planilha, tmp_path)
    _escolher(at, "Moradores — cadastro completo (identificado)")
    assert not at.exception
    texto = at.dataframe[0].value.to_csv(index=False)
    assert "Pessoa Ficticia" in texto  # admin vê nomes
    assert not any(cpf in texto for cpf in modelo[0]["morador"]["cpf"].dropna())  # CPF só mascarado
    assert any("ciente" in c.label.lower() or "ciente" in str(c.label).lower() for c in at.checkbox)


def test_publico_nao_tem_microdados_nem_identificados(planilha, tmp_path):
    at = rodar("dados", "publico", planilha, tmp_path)
    opcoes = list(at.selectbox(key="dl_tabela").options)
    assert all("agregada" in o or "Indicadores" in o for o in opcoes)


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


def test_k_igual_a_1_nao_omite_nada_no_publico(planilha, tmp_path):
    script = SCRIPT.replace("construir_ctx({nivel!r}, {xlsx!r}, {log!r})",
                            "construir_ctx({nivel!r}, {xlsx!r}, {log!r}, k=1)")
    at = AppTest.from_string(script.format(root=str(ROOT), nivel="publico", xlsx=str(planilha), pagina="atividades",
                                           log=str(tmp_path / "log.csv")), default_timeout=60).run()
    assert not at.exception
    assert not any("omitidos" in str(c.value) for c in at.caption)
    ultima = [d.value for d in at.dataframe][-1].astype(str).to_numpy().ravel()
    assert not any(str(v).startswith("<") for v in ultima)


def test_config_k_padroes_e_independentes(monkeypatch):
    from mondo import config
    base = {"privacy.k_min": 1}
    monkeypatch.setattr(config, "secret", lambda path, default=None: base.get(path, default))
    s = config.get_settings()
    assert (s.k_min, s.k_sensivel, s.k_download) == (1, 5, 5)  # relaxar o geral não relaxa saúde nem download


def test_acesso_externo_detecta_tunel():
    from mondo.auth import acesso_externo
    assert acesso_externo({"Host": "localhost:8501", "Cf-Connecting-Ip": "1.2.3.4"})
    assert acesso_externo({"x-forwarded-for": "1.2.3.4"})
    assert not acesso_externo({"Host": "localhost:8501", "User-Agent": "x"})


def test_senha_da_equipe_bloqueia_tudo_ate_acertar(planilha, monkeypatch, tmp_path):
    monkeypatch.delenv("MONDO_DEV", raising=False)
    monkeypatch.setattr("time.sleep", lambda s: None)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.secrets["data"] = {"xlsx_path": str(planilha)}
    at.secrets["privacy"] = {"pseudo_secret": "segredo-de-teste"}
    at.secrets["access"] = {"team_password": "abc123"}
    at.secrets["audit"] = {"path": str(tmp_path / "log.csv")}
    at.run()
    assert not at.exception and len(at.metric) == 0 and at.text_input(key="senha_equipe")
    at.text_input(key="senha_equipe").set_value("errada").run()
    assert any("incorreta" in e.value for e in at.error) and len(at.metric) == 0
    assert "errada" not in (tmp_path / "log.csv").read_text(encoding="utf-8")
    at.text_input(key="senha_equipe").set_value("abc123").run()
    assert not at.exception and len(at.metric) > 0


def test_feedback_e_gravado_e_aparece_no_admin(planilha, tmp_path):
    script = f"""
import sys; sys.path.insert(0, {str(ROOT)!r})
from types import SimpleNamespace
from pathlib import Path
from mondo import feedback
feedback.caixa(SimpleNamespace(log_path=Path({str(tmp_path / 'log.csv')!r})), "Visão geral", {{"ano": [2025]}})
"""
    at = AppTest.from_string(script, default_timeout=30).run()
    at.sidebar.text_area[0].set_value("O gráfico de saúde ficou ótimo")  # em formulário, valor e envio vão juntos
    next(b for b in at.sidebar.button if b.label == "Enviar").click().run()
    assert not at.exception
    texto = (tmp_path / "feedback.csv").read_text(encoding="utf-8")
    assert "gráfico de saúde" in texto and "Visão geral" in texto
    pg = rodar("feedback_admin", "admin", planilha, tmp_path)
    assert not pg.exception and len(pg.dataframe) == 1


def test_bloqueio_global_apos_muitas_senhas_erradas(planilha, monkeypatch, tmp_path):
    import streamlit as st
    st.cache_resource.clear()
    monkeypatch.delenv("MONDO_DEV", raising=False)
    monkeypatch.setattr("time.sleep", lambda s: None)

    def nova_sessao():
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
        at.secrets["data"] = {"xlsx_path": str(planilha)}
        at.secrets["privacy"] = {"pseudo_secret": "segredo-de-teste"}
        at.secrets["access"] = {"team_password": "abc123"}
        at.secrets["audit"] = {"path": str(tmp_path / "log.csv")}
        return at.run()

    for _ in range(8):  # 8 sessões diferentes, cada uma erra uma vez
        at = nova_sessao()
        at.text_input(key="senha_equipe").set_value("errada").run()
    at = nova_sessao()
    assert any("Muitas tentativas" in e.value for e in at.error) and len(at.text_input) == 0 and len(at.metric) == 0
    st.cache_resource.clear()
