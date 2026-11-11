"""Testes contra um PostgreSQL de verdade (pgserver). Pulados se o pacote não estiver instalado."""
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

pgserver = pytest.importorskip("pgserver")
sa = pytest.importorskip("sqlalchemy")

from mondo import audit, carga, feedback, loader, mascaramento  # noqa: E402
from mondo.loader import cpf_valido  # noqa: E402
from mondo.metrics import fato_participacao, kpis, morador_enriquecido  # noqa: E402
from tests.fixtures import NOMES_FICTICIOS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REF = date(2026, 11, 4)


@pytest.fixture(scope="session")
def servidor():
    d = tempfile.mkdtemp()
    srv = pgserver.get_server(d, cleanup_mode="stop")
    yield srv.get_uri().replace("postgresql://", "postgresql+psycopg2://")
    srv.cleanup()


@pytest.fixture()
def banco(servidor):
    """Banco limpo a cada teste (recria os schemas)."""
    eng = sa.create_engine(servidor)
    with eng.begin() as c:
        c.exec_driver_sql("drop schema if exists core cascade; drop schema if exists acesso cascade;")
    carga.criar_esquema(eng)
    yield servidor, eng
    eng.dispose()


def _kpis(frames):
    mor = morador_enriquecido(frames, REF)
    return kpis(frames, fato_participacao(frames, mor), mor)


def test_esquema_idempotente_e_com_rls(banco):
    url, eng = banco
    carga.criar_esquema(eng)  # segunda execução não pode falhar
    with eng.connect() as c:
        tabelas = c.execute(sa.text("select tablename, rowsecurity from pg_tables where schemaname in ('core','acesso')")).all()
    assert len(tabelas) >= 25 and all(rls for _, rls in tabelas)  # RLS ligado em todas


def test_ida_e_volta_preserva_os_numeros(banco, modelo):
    url, eng = banco
    frames, quali = modelo
    resumo = carga.carregar(eng, frames, quali, mascarado=False, origem="teste.xlsx")
    assert resumo["participacao"] == len(frames["participacao"])
    lidos, quali_lida, info = loader.carregar_postgres(url)
    assert info["mascarado"] is False and info["origem"] == "teste.xlsx"
    for t, df in frames.items():
        assert len(lidos[t]) == len(df), t
    assert _kpis(lidos) == _kpis(frames)
    assert len(quali_lida) == len(quali) and (quali_lida["ocorrencias"].sum() == quali["ocorrencias"].sum())
    assert str(lidos["morador"]["ciclo"].dtype) == "Int64" and str(lidos["avaliacao"]["turno_tarde"].dtype) == "boolean"
    assert pd.api.types.is_datetime64_any_dtype(lidos["oferta"]["data_inicio"])


def test_carga_mascarada_marca_o_banco_e_troca_identificacoes(banco, modelo):
    url, eng = banco
    frames, quali = modelo
    mask = mascaramento.mascarar(frames, "semente-x", REF)
    carga.carregar(eng, mask, quali, mascarado=True, origem="teste.xlsx")
    lidos, _, info = loader.carregar_postgres(url)
    assert info["mascarado"] is True
    texto = lidos["morador"].to_csv(index=False) + lidos["familia"].to_csv(index=False) + lidos["participante"].to_csv(index=False)
    assert not any(n in texto for n in NOMES_FICTICIOS) and "Responsavel Ficticio" not in texto and "Rua Inventada" not in texto
    assert all(cpf_valido(c) for c in lidos["morador"]["cpf"].dropna())
    assert not set(lidos["morador"]["cpf"].dropna()) & set(frames["morador"]["cpf"].dropna())
    assert _kpis(lidos) == _kpis(frames)  # números idênticos
    orig = frames["morador"].set_index("id_morador")
    novo = lidos["morador"].set_index("id_morador")
    assert (orig["sexo"] == novo["sexo"]).all() and (orig["status"] == novo["status"]).all()
    from mondo.privacy import faixa_etaria, idade_em
    assert (faixa_etaria(idade_em(orig["data_nascimento"], REF)).fillna("") == faixa_etaria(idade_em(novo["data_nascimento"], REF)).fillna("")).all()


def test_mascaramento_nao_altera_o_original_e_e_deterministico(modelo):
    frames, _ = modelo
    antes = frames["morador"]["nome"].copy()
    a = mascaramento.mascarar(frames, "s1", REF)
    b = mascaramento.mascarar(frames, "s1", REF)
    c = mascaramento.mascarar(frames, "s2", REF)
    assert frames["morador"]["nome"].equals(antes)
    assert a["morador"]["cpf"].equals(b["morador"]["cpf"]) and not a["morador"]["cpf"].equals(c["morador"]["cpf"])
    assert a["avaliacao"]["elogios_texto"].dropna().eq(mascaramento.TEXTO_REMOVIDO).all()
    assert a["familia"]["latitude"].notna().sum() == frames["familia"]["latitude"].notna().sum()


def test_sequencias_continuam_depois_da_carga(banco, modelo):
    url, eng = banco
    frames, quali = modelo
    carga.carregar(eng, frames, quali, mascarado=True, origem="t")
    with eng.begin() as c:
        novo = c.execute(sa.text("insert into core.morador (codigo_morador, nome) values ('999.1', 'Novo') returning id_morador")).scalar()
    assert novo == frames["morador"]["id_morador"].max() + 1


def test_recarga_e_protegida_quando_ha_dados_dependentes(banco, modelo):
    url, eng = banco
    frames, quali = modelo
    carga.carregar(eng, frames, quali, mascarado=True, origem="t")
    with eng.begin() as c:
        dim = c.execute(sa.text("select min(id_dimensao) from core.dimensao")).scalar()
        c.execute(sa.text("insert into core.rubrica (id_dimensao, descricao) values (:d, 'rubrica manual')"), {"d": dim})
    with pytest.raises(sa.exc.IntegrityError):  # sem --reset o banco recusa e NADA é apagado
        carga.carregar(eng, frames, quali, mascarado=True, origem="t")
    with eng.connect() as c:
        assert c.execute(sa.text("select count(*) from core.morador")).scalar() == len(frames["morador"])
    carga.carregar(eng, frames, quali, mascarado=True, origem="t", reset=True)  # com reset, funciona
    with eng.connect() as c:
        assert c.execute(sa.text("select count(*) from core.rubrica")).scalar() == 0


def test_auditoria_e_feedback_persistem_no_banco(banco, tmp_path):
    url, eng = banco
    st.cache_resource.clear()
    s = SimpleNamespace(backend="postgres", postgres_url=url, log_path=tmp_path / "log.csv")
    audit.registrar(s, "a@x.com", "admin", "download_tabela", "moradores", filtros={"ano": ["2025"]}, linhas=10)
    log = audit.ler(s)
    assert len(log) == 1 and log.loc[0, "acao"] == "download_tabela" and "2025" in log.loc[0, "filtros"]
    feedback.registrar(s, "Ana", "Sugestão", "Visão geral", "Ficou ótimo", {"ano": [2025]})
    fb = feedback.ler(s)
    assert len(fb) == 1 and fb.loc[0, "texto"] == "Ficou ótimo"
    assert not (tmp_path / "log.csv").exists() and not (tmp_path / "feedback.csv").exists()  # nada foi para o disco


def _app(url, tmp_path, nivel):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.secrets["data"] = {"backend": "postgres", "postgres_url": url}
    at.secrets["privacy"] = {"pseudo_secret": "segredo-de-teste", "k_min": 1, "k_sensivel": 1, "k_explorador": 1}
    at.secrets["access"] = {"team_password": "abc123", "team_level": nivel}
    at.secrets["audit"] = {"path": str(tmp_path / "log.csv")}
    return at


def test_app_no_banco_admin_por_senha_so_com_dados_de_teste(banco, modelo, tmp_path, monkeypatch):
    url, eng = banco
    frames, quali = modelo
    monkeypatch.delenv("MONDO_DEV", raising=False)
    monkeypatch.setattr("time.sleep", lambda s: None)
    st.cache_resource.clear()

    carga.carregar(eng, mascaramento.mascarar(frames, "s", REF), quali, mascarado=True, origem="t")
    at = _app(url, tmp_path, "admin").run()
    at.text_input(key="senha_equipe").set_value("abc123").run()
    assert not at.exception
    assert any("TESTE" in str(i.value) for i in at.sidebar.info)             # banner de ambiente de teste
    assert any("Acesso da equipe" in str(c.value) for c in at.sidebar.caption)
    assert any("Administrador" in str(c.value) for c in at.sidebar.caption)  # nível efetivo: administrador
    assert len(at.metric) > 0

    st.cache_resource.clear()
    carga.carregar(eng, frames, quali, mascarado=False, origem="t")          # agora com dados REAIS (não mascarados)
    at = _app(url, tmp_path, "admin").run()
    at.text_input(key="senha_equipe").set_value("abc123").run()
    assert not at.exception
    assert any("só é permitido com dados de TESTE" in str(e.value) for e in at.sidebar.error)
    assert any("Público" in str(c.value) for c in at.sidebar.caption)       # ficou no nível público
    st.cache_resource.clear()
