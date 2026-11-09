"""Páginas do app. Cada função recebe o contexto (Ctx) do nível de acesso atual."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import audit
from .config import ROOT
from .exportacao import montar_pacote
from .metrics import (INT_COLS, NAO_INFORMADO, TURNO_COLS, catalogo, contar, kpis, medias_questoes, percentual,
                      proporcoes)
from .privacy import para_pesquisa
from .ui import Ctx, barras, linhas_tempo, rosca, tabela, vazio


def _rotulo(df: pd.DataFrame, col: str) -> pd.DataFrame:
    out = df.copy()
    out[col] = out[col].astype(object).where(out[col].notna(), NAO_INFORMADO)
    return out


def _pct(v) -> str:
    return "—" if v is None else f"{v:.1f}%".replace(".", ",")


# ================================================================== visão geral
def visao_geral(c: Ctx) -> None:
    st.title("Visão geral")
    st.caption("Famílias e moradores mostram o cadastro completo; participações e ofertas respeitam os filtros da barra lateral.")
    if vazio(c.fato):
        return
    kp = kpis(c.frames, c.fato, c.mor)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Famílias cadastradas", c.n(kp["familias"]))
    k2.metric("Moradores ativos", c.n(kp["moradores_ativos"]))
    k3.metric("Participantes únicos", c.n(kp["participantes"]))
    k4.metric("Cobertura dos moradores ativos", _pct(kp["cobertura_pct"]),
              help="Moradores ativos com ao menos uma participação no período filtrado.")
    k5, k6, k7, _ = st.columns(4)
    k5.metric("Participações", c.n(kp["participacoes"]))
    k6.metric("Ofertas realizadas", c.n(kp["ofertas"]))
    k7.metric("Atividades diferentes", c.n(kp["atividades"]))

    linhas_tempo(c, contar(c.fato, ["mes", "dimensao"]), "mes", cor="dimensao", titulo="Participações por mês e dimensão")
    barras(c, contar(c.fato, "dimensao", distinto="id_participante"), "dimensao", horizontal=True,
           titulo="Participantes únicos por dimensão")


# ================================================================== atividades
def atividades(c: Ctx) -> None:
    st.title("Atividades")
    if vazio(c.fato):
        return
    t1, t2, t3 = st.tabs(["Por dimensão e categoria", "Mais frequentadas", "Lista completa"])
    with t1:
        barras(c, contar(c.fato, ["dimensao", "categoria"]), "dimensao", cor="categoria", empilhar=True,
               titulo="Participações por dimensão e categoria")
        of = c.fato.groupby(["ano", "dimensao"])["id_oferta"].nunique().rename("valor").reset_index()
        of["ano"] = of["ano"].astype(int).astype(str)
        barras(c, of, "ano", cor="dimensao", titulo="Ofertas realizadas por ano e dimensão", sensivel=False,
               empilhar=True)
    with t2:
        top = contar(c.fato, "atividade", distinto="id_participante").nlargest(15, "valor")
        barras(c, top, "atividade", horizontal=True, titulo="15 atividades com mais participantes únicos")
    with t3:
        t = (c.fato.groupby("atividade")
             .agg(dimensao=("dimensao", "first"), categoria=("categoria", "first"),
                  ofertas=("id_oferta", "nunique"), participacoes=("id_participacao", "size"),
                  participantes=("id_participante", "nunique")).reset_index().sort_values("participantes", ascending=False))
        tabela(c, t, ["participacoes", "participantes"])


# ================================================================== território
def territorio(c: Ctx) -> None:
    st.title("Território")
    ativos = _rotulo(_rotulo(c.mor[c.mor["status"] == "Ativa"], "comunidade"), "zona")
    mapa = c.admin and "latitude" in c.frames["familia"].columns
    abas = st.tabs(["Moradores por comunidade", "Participações por comunidade da atividade"]
                   + (["Mapa das famílias"] if mapa else []))
    with abas[0]:
        a, b = st.columns([2, 1])
        with a:
            barras(c, contar(ativos, "comunidade"), "comunidade", horizontal=True, titulo="Moradores ativos por comunidade")
        with b:
            rosca(c, contar(ativos, "zona"), "zona", titulo="Moradores ativos por zona")
    with abas[1]:
        st.caption("Comunidade informada na linha da atividade (o significado exato está em validação).")
        d = c.fato[c.fato["comunidade_atividade"] != NAO_INFORMADO]
        barras(c, contar(d, "comunidade_atividade").nlargest(20, "valor"), "comunidade_atividade", horizontal=True,
               titulo="20 comunidades com mais participações")
    if mapa:
        with abas[2]:
            st.warning("A localização das casas é dado pessoal: visível somente ao administrador.")
            pts = c.frames["familia"][["latitude", "longitude"]].dropna()
            st.map(pts)
            st.caption(f"{len(pts)} famílias com coordenadas.")


# ================================================================== perfil
def perfil(c: Ctx) -> None:
    st.title("Perfil dos moradores")
    ativos = c.mor[c.mor["status"] == "Ativa"]
    a, b = st.columns(2)
    with a:
        rosca(c, contar(_rotulo(ativos, "sexo"), "sexo"), "sexo", titulo="Moradores ativos por sexo")
    with b:
        barras(c, contar(_rotulo(ativos, "faixa_etaria"), "faixa_etaria"), "faixa_etaria",
               titulo="Moradores ativos por faixa etária")
    part = c.fato[c.fato["origem"] == "cadastro"].drop_duplicates("id_participante")
    barras(c, contar(part, "faixa_etaria"), "faixa_etaria", titulo="Participantes do cadastro por faixa etária")
    if c.restrito:
        st.subheader("Perfil socioeconômico e situação")
        st.caption("Os significados de ciclo, grupo e IPM estão em validação com o Instituto.")
        x, y = st.columns(2)
        with x:
            barras(c, contar(c.mor.assign(ciclo=c.mor["ciclo"].astype("string").fillna(NAO_INFORMADO)), "ciclo"),
                   "ciclo", titulo="Moradores por ciclo")
        with y:
            barras(c, contar(c.mor.assign(status=c.mor["status"].fillna(NAO_INFORMADO)), "status"), "status",
                   titulo="Moradores por situação")
        ipm = c.mor.assign(ipm=c.mor["ipm"].astype("string").fillna(NAO_INFORMADO))
        barras(c, contar(ipm, "ipm"), "ipm", titulo="Moradores por valor de IPM")
    else:
        st.info("Ciclo, grupo e IPM ficam disponíveis para pesquisadores autorizados.")


# ================================================================== saúde
def saude(c: Ctx) -> None:
    st.title("Saúde")
    st.info("Dados de saúde são dados pessoais sensíveis (LGPD, art. 5º, II). Aqui aparecem apenas totais; "
            "nada identifica pessoas.")
    d = c.fato[c.fato["dimensao"].astype(str).str.upper() == "SAÚDE"]
    if vazio(d):
        return
    abas = st.tabs(["Por especialidade", "Evolução"] + (["Perfil de quem participou"] if c.restrito else []))
    with abas[0]:
        por_tipo = contar(d, "tipo", distinto="id_participante")
        barras(c, por_tipo, "tipo", horizontal=True, titulo="Participantes únicos por especialidade/tipo")
        tabela(c, por_tipo.rename(columns={"valor": "participantes"}).sort_values("participantes", ascending=False),
               ["participantes"])
    with abas[1]:
        top_tipos = contar(d, "tipo").nlargest(8, "valor")["tipo"]
        linhas_tempo(c, contar(d[d["tipo"].isin(top_tipos)], ["ano", "tipo"]).assign(ano=lambda t: t["ano"].astype(int).astype(str)),
                     "ano", cor="tipo", titulo="Participações por ano (8 tipos mais frequentes)")
    if c.restrito:
        with abas[2]:
            u = d.drop_duplicates("id_participante")
            barras(c, contar(_rotulo(_rotulo(u, "sexo"), "faixa_etaria"), ["faixa_etaria", "sexo"], distinto="id_participante"),
                   "faixa_etaria", cor="sexo", titulo="Participantes únicos de saúde por faixa etária e sexo")


# ================================================================== doações e cestas
def doacoes(c: Ctx) -> None:
    st.title("Doações e cestas básicas")
    d = c.fato
    if vazio(d):
        return
    dd, cc = d[d["doacao"]], d[d["cesta_basica"]]
    k1, k2, k3 = st.columns(3)
    k1.metric("Participações com doação", c.n(len(dd)))
    k2.metric("Participações com cesta básica", c.n(len(cc)))
    k3.metric("Pessoas que receberam doação ou cesta", c.n(d[d["doacao"] | d["cesta_basica"]]["id_participante"].nunique()))
    itens = contar(dd.assign(item_doacao=dd["item_doacao"].replace(NAO_INFORMADO, "Doação sem item informado")), "item_doacao")
    barras(c, itens, "item_doacao", horizontal=True, titulo="Doações por item")
    cestas = contar(cc, "ano").assign(ano=lambda t: t["ano"].astype(int).astype(str))
    barras(c, cestas, "ano", titulo="Participações com cesta básica por ano")


# ================================================================== avaliações
def avaliacoes(c: Ctx) -> None:
    st.title("Avaliações das formações")
    av = c.av
    dims = ["Todas"] + sorted(av["dimensao"].dropna().unique())
    sel = st.selectbox("Dimensão", dims)
    if sel != "Todas":
        av = av[av["dimensao"] == sel]
    if vazio(av):
        return
    nota = pd.to_numeric(av["nota_geral"], errors="coerce")
    q4 = pd.to_numeric(av["q04_recomendacao"], errors="coerce").dropna()
    k1, k2, k3 = st.columns(3)
    k1.metric("Respostas", c.n(len(av)))
    k2.metric("Nota geral média", "—" if nota.dropna().empty or (c.publico and nota.notna().sum() < c.k)
              else f"{nota.mean():.2f}".replace(".", ","))
    k3.metric("Recomendariam (notas 4 e 5)", "—" if q4.empty or (c.publico and len(q4) < c.k)
              else _pct(percentual(int((q4 >= 4).sum()), len(q4))))

    m = medias_questoes(av)
    if c.publico:
        m = m[m["respostas"] >= c.k]
    barras(c, m, "questao", y="media", horizontal=True, titulo="Média por pergunta", sensivel=False)

    ev = (av.assign(nota=nota).groupby("evento").agg(respostas=("id_avaliacao", "size"), nota_media=("nota", "mean"))
          .reset_index().sort_values("respostas", ascending=False))
    if c.publico:
        ev = ev[ev["respostas"] >= c.k]
    ev["nota_media"] = ev["nota_media"].round(2)
    st.subheader("Por formação ou evento")
    tabela(c, ev)

    a, b = st.columns(2)
    for col, base, titulo in ((a, INT_COLS, "O que pretendem fazer após a formação"), (b, TURNO_COLS, "Turno preferido")):
        p = proporcoes(av, base)
        if c.publico:
            p = p[p["respondentes"] >= c.k]
        with col:
            barras(c, p, "opcao", y="percentual", horizontal=True, titulo=titulo, sensivel=False, rotulo_y="% dos respondentes")
    dist = contar(av.assign(nota=(nota * 2).round() / 2).dropna(subset=["nota"]), "nota")
    barras(c, dist, "nota", titulo="Distribuição da nota geral (arredondada a 0,5)")


# ================================================================== indicadores
def indicadores(c: Ctx) -> None:
    st.title("Indicadores")
    st.caption("Indicadores calculáveis com os dados atuais. Metas, pesos e indicadores formais entram quando "
               "as demais fontes (projetos, rubricas) forem incluídas.")
    t = catalogo(c.frames, c.fato, c.mor, c.av, c.k, c.publico)
    if c.publico:
        t = t[t["Nível mínimo"] == "P"]
    t = t.assign(**{"Nível mínimo": t["Nível mínimo"].map({"P": "Público", "R": "Pesquisador"})})
    st.dataframe(t, hide_index=True)


# ================================================================== dados para pesquisa
def dados_pesquisa(c: Ctx) -> None:
    st.title("Dados para pesquisa")
    st.markdown("Baixe dados **pseudonimizados** para análises e modelos. Nomes, CPF, telefone, endereços, coordenadas "
                "e textos livres são removidos; identificadores viram códigos; idade vira faixa etária.")
    termo = (ROOT / "TERMO_DE_USO.md")
    with st.expander("Termo de uso (leia antes de baixar)", expanded=not st.session_state.get("termo_ok", False)):
        st.markdown(termo.read_text(encoding="utf-8") if termo.exists() else "Termo de uso não encontrado.")
    aceito = st.checkbox("Li e aceito o termo de uso", key="termo_ok")
    if not aceito:
        st.warning("Aceite o termo de uso para gerar o pacote.")
        return
    if not c.settings.pseudo_secret:
        st.error("A chave de pseudonimização não está configurada (privacy.pseudo_secret). Peça ao administrador.")
        return
    st.caption(f"Proteção adicional: cada combinação de comunidade, faixa etária, sexo e zona tem ao menos k = {c.k} moradores.")
    if st.button("Gerar pacote de dados", type="primary"):
        with st.spinner("Gerando arquivos…"):
            pacote, resumo, rel = montar_pacote(c.frames, c.ref, c.k, c.email or "dev")
        st.session_state["pacote"] = (pacote, resumo, rel)
        audit.registrar(c.settings, c.email, c.nivel, "gerar_pacote", "pacote_pseudonimizado",
                        linhas=int(resumo["linhas"].sum()))
    if "pacote" in st.session_state:
        pacote, resumo, rel = st.session_state["pacote"]
        st.dataframe(resumo, hide_index=True)
        st.caption(f"k-anonimato em moradores: menor grupo {rel['menor_grupo_antes']} → {rel['menor_grupo_depois']}; "
                   f"{rel['linhas_alteradas']} de {rel['linhas']} linhas tiveram comunidade/faixa/zona/sexo generalizados ou apagados.")
        st.download_button(
            "Baixar pacote (.zip)", pacote, file_name="mondo_dados_pseudonimizados.zip", mime="application/zip",
            on_click=lambda: audit.registrar(c.settings, c.email, c.nivel, "download", "pacote_pseudonimizado",
                                             linhas=int(resumo["linhas"].sum())))


# ================================================================== administração
def qualidade(c: Ctx) -> None:
    st.title("Qualidade dos dados")
    st.caption(f"Carga: {c.carregado_em}")
    if c.qualidade.empty:
        st.info("O relatório de qualidade é gerado na carga da planilha.")
    else:
        q = c.qualidade.rename(columns={"id": "ID", "problema": "Problema", "ocorrencias": "Ocorrências",
                                        "base": "Base", "percentual": "%"})
        st.dataframe(q, hide_index=True)
    st.subheader("Tabelas carregadas")
    st.dataframe(pd.DataFrame([{"tabela": n, "linhas": len(d), "colunas": d.shape[1]} for n, d in c.frames.items()]),
                 hide_index=True)
    st.subheader("Preenchimento das colunas")
    nome = st.selectbox("Tabela", list(c.frames))
    d = c.frames[nome]
    st.dataframe(pd.DataFrame({"coluna": d.columns, "preenchido_%": (100 * d.notna().mean()).round(1).values}),
                 hide_index=True)
    if st.button("Recarregar dados da fonte"):
        st.cache_resource.clear()
        st.rerun()


def cadastro(c: Ctx) -> None:
    st.title("Consulta ao cadastro")
    st.warning("Acesso restrito a administradores. Dados pessoais: cada consulta é registrada (sem o texto buscado).")
    termo = st.text_input("Buscar por nome, código do morador (ex.: 12.3) ou CPF")
    revelar = st.checkbox("Mostrar CPF e telefone completos")
    if not termo.strip():
        return
    m = c.frames["morador"]
    t = termo.strip().lower()
    dig = "".join(ch for ch in t if ch.isdigit())
    mask = (m["nome"].fillna("").str.lower().str.contains(t, regex=False)
            | m["codigo_morador"].fillna("").str.lower().eq(t)
            | (m["cpf"].fillna("").eq(dig) if len(dig) >= 8 else False))
    res = m[mask].head(200).copy()
    audit.registrar(c.settings, c.email, c.nivel, "consulta_cadastro", "morador", linhas=len(res))
    if res.empty:
        st.info("Nada encontrado.")
        return
    res["idade"] = c.mor.set_index("id_morador").reindex(res["id_morador"])["idade"].values
    if not revelar:
        res["cpf"] = res["cpf"].map(lambda v: None if not isinstance(v, str) else f"***.{v[3:6]}.{v[6:9]}-**")
        res["telefone"] = res["telefone"].map(lambda v: None if not isinstance(v, str) else f"(**) *****-{v[-4:]}")
    else:
        audit.registrar(c.settings, c.email, c.nivel, "revelar_cpf_telefone", "morador", linhas=len(res))
    st.dataframe(res[["codigo_morador", "nome", "sexo", "idade", "cpf", "telefone", "status", "ciclo", "grupo"]],
                 hide_index=True)
    st.caption(f"{len(res)} resultado(s) (máximo de 200 exibidos).")


def acessos(c: Ctx) -> None:
    from .auth import _admins, _pesquisadores
    st.title("Acessos e auditoria")
    a, b = st.columns(2)
    with a:
        st.subheader("Administradores")
        st.dataframe(pd.DataFrame({"e-mail": sorted(_admins())}), hide_index=True)
    with b:
        st.subheader("Pesquisadores autorizados")
        pesq = _pesquisadores()
        st.dataframe(pd.DataFrame([{"e-mail": e, "validade": v or "sem prazo"} for e, v in sorted(pesq.items())]),
                     hide_index=True)
    st.caption("As listas vêm de .streamlit/secrets.toml (seção [access]). Para alterar, edite o arquivo e reinicie o app.")
    st.subheader("Registro de acessos")
    log = audit.ler(c.settings)
    if log.empty:
        st.info("Nenhum evento registrado ainda.")
    else:
        st.dataframe(log, hide_index=True)
        st.download_button("Baixar log (.csv)", log.to_csv(index=False), file_name="log_acesso.csv", mime="text/csv")


# ================================================================== sobre
def sobre(c: Ctx) -> None:
    st.title("Sobre estes dados")
    ini, fim = c.fato_total["data_inicio"].min(), c.fato_total["data_fim"].max()
    st.markdown(f"""
**Fonte:** planilha de bases de dados do Instituto Mondó (famílias, moradores, atividades e avaliações).
**Período das atividades:** {ini:%d/%m/%Y} a {fim:%d/%m/%Y}. **Última carga:** {c.carregado_em}.

**Níveis de acesso**
- **Público:** somente números agregados. Valores menores que **{c.k}** são omitidos (aparecem como “<{c.k}”) e, quando
  necessário, outro valor é omitido junto para impedir a recuperação por subtração.
- **Pesquisador:** login com Google, autorização prévia e termo de uso; recebe dados pseudonimizados.
- **Administrador:** acesso completo, com registro de todas as consultas.

**Cuidados com os dados (LGPD):** nomes, CPF, telefones, endereços e localização das casas nunca aparecem fora do nível
de administrador. Parte dos participantes é de crianças e adolescentes, e há dados de saúde; por isso o painel público
não mostra cruzamentos que possam identificar pessoas.

**Limites:** a planilha ainda está sendo completada. Há registros duplicados e vínculos incompletos que são tratados na
carga (veja “Qualidade dos dados”, para administradores). Os significados de *ciclo*, *grupo* e *IPM* estão em validação.
""")
    st.caption("Este painel não substitui relatórios oficiais. Dúvidas: fale com a equipe do Instituto.")
