"""Pesquisadores autorizados guardados no banco (tabela acesso.acesso_pesquisador).

Fluxo:
  1. A pessoa entra com a conta Google (o Google só confirma QUEM ela é, não o que ela pode ver).
  2. Se não tiver autorização, aparece o formulário "Solicitar acesso": fica como `pendente`.
  3. O administrador aprova (com validade) ou recusa na página "Acessos e auditoria". Também pode convidar por e-mail.
  4. Aprovado e dentro da validade = nível Pesquisador. Revogado/expirado/pendente = Público.

Administradores continuam só na lista access.admins do secrets.toml (ninguém vira admin pelo banco).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from . import audit, db

VALIDADES = {"6 meses": 183, "1 ano": 365, "2 anos": 730, "Sem prazo": None}
STATUS_ROTULO = {"pendente": "Pendente", "aprovado": "Aprovado", "revogado": "Revogado"}


# ------------------------------------------------------------------ regra (sem banco, fácil de testar)
def situacao(reg: dict | None, agora: datetime | None = None) -> tuple[bool, str | None]:
    """(tem_acesso_de_pesquisador, aviso) para um registro da tabela. Sem registro = sem acesso e sem aviso."""
    agora = agora or datetime.now(timezone.utc)
    if not reg:
        return False, None
    status = str(reg.get("status") or "").lower()
    if status == "aprovado":
        exp = reg.get("expira_em")
        if exp is not None and not pd.isna(exp):
            exp = pd.Timestamp(exp)
            exp = exp.tz_localize("UTC") if exp.tzinfo is None else exp.tz_convert("UTC")
            if exp < pd.Timestamp(agora):
                return False, "Sua autorização de pesquisador expirou. Solicite renovação no formulário abaixo."
        return True, None
    if status == "pendente":
        return False, "Sua solicitação de acesso está em análise. Você será avisado pelo administrador."
    if status == "revogado":
        return False, "Seu acesso foi revogado. Fale com o administrador do banco."
    return False, None


# ------------------------------------------------------------------ banco
def _engine(settings):
    return db.engine(settings.postgres_url)


def buscar(settings, email: str) -> dict | None:
    from sqlalchemy import text
    with _engine(settings).connect() as conn:
        linha = conn.execute(text("select email, nome, status, expira_em from acesso.acesso_pesquisador "
                                  "where lower(email) = :e"), {"e": email.strip().lower()}).mappings().first()
    return dict(linha) if linha else None


def solicitar(settings, email: str, nome: str, instituicao: str, finalidade: str) -> None:
    """Cria (ou atualiza, se ainda pendente ou vencida) a solicitação. Revogados não se reativam sozinhos."""
    from sqlalchemy import text
    with _engine(settings).begin() as conn:
        conn.execute(text(
            "insert into acesso.acesso_pesquisador (email, nome, instituicao, finalidade, status, termo_aceito_em) "
            "values (:e, :n, :i, :f, 'pendente', now()) "
            "on conflict (email) do update set nome = :n, instituicao = :i, finalidade = :f, status = 'pendente', "
            "termo_aceito_em = now(), expira_em = null "
            "where acesso.acesso_pesquisador.status = 'pendente' "
            "or (acesso.acesso_pesquisador.status = 'aprovado' and acesso.acesso_pesquisador.expira_em < now())"),
            {"e": email.strip().lower(), "n": nome.strip()[:200], "i": instituicao.strip()[:200],
             "f": finalidade.strip()[:1000]})


def listar(settings) -> pd.DataFrame:
    from sqlalchemy import text
    with _engine(settings).connect() as conn:
        df = pd.read_sql(text(
            "select email, nome, instituicao, finalidade, status, termo_aceito_em, aprovado_por, expira_em "
            "from acesso.acesso_pesquisador "
            "order by case status when 'pendente' then 0 when 'aprovado' then 1 else 2 end, email"), conn)
    return df


def decidir(settings, email: str, status: str, por: str, dias: int | None = None) -> None:
    """Aprova (com validade em dias, ou sem prazo se None), recusa/revoga ('revogado') ou volta a 'pendente'."""
    from sqlalchemy import text
    if status not in STATUS_ROTULO:
        raise ValueError(status)
    expira = datetime.now(timezone.utc) + timedelta(days=dias) if (status == "aprovado" and dias) else None
    with _engine(settings).begin() as conn:
        conn.execute(text("update acesso.acesso_pesquisador set status = :s, aprovado_por = :p, expira_em = :x "
                          "where lower(email) = :e"),
                     {"s": status, "p": por, "x": expira, "e": email.strip().lower()})


def convidar(settings, email: str, nome: str, por: str, dias: int | None = None) -> None:
    """Autoriza um e-mail direto (sem a pessoa pedir). O termo de uso ainda será exibido no primeiro download."""
    from sqlalchemy import text
    expira = datetime.now(timezone.utc) + timedelta(days=dias) if dias else None
    with _engine(settings).begin() as conn:
        conn.execute(text(
            "insert into acesso.acesso_pesquisador (email, nome, status, aprovado_por, expira_em) "
            "values (:e, :n, 'aprovado', :p, :x) "
            "on conflict (email) do update set nome = :n, status = 'aprovado', aprovado_por = :p, expira_em = :x"),
            {"e": email.strip().lower(), "n": nome.strip()[:200] or email.strip(), "p": por, "x": expira})


# ------------------------------------------------------------------ telas
def formulario_solicitacao(settings, email: str) -> None:
    """Barra lateral: pedido de acesso de pesquisador (para quem entrou com Google mas não tem autorização)."""
    try:
        reg = buscar(settings, email)
    except Exception:
        return
    if reg and str(reg.get("status")).lower() in ("pendente", "revogado"):
        return  # já pediu (aviso exibido pelo auth) ou foi revogado (precisa falar com o administrador)
    with st.sidebar.expander("Solicitar acesso de pesquisador"):
        with st.form("form_solicitacao", clear_on_submit=False):
            nome = st.text_input("Nome completo", max_chars=200)
            inst = st.text_input("Instituição", max_chars=200)
            fin = st.text_area("Para que você vai usar os dados?", max_chars=1000)
            termo = st.checkbox("Li e aceito o termo de uso (LGPD): uso apenas para a finalidade informada, "
                                "sem tentar reidentificar pessoas e sem compartilhar os arquivos.")
            enviado = st.form_submit_button("Enviar solicitação")
        if enviado:
            if not (nome.strip() and fin.strip() and termo):
                st.warning("Preencha nome e finalidade e aceite o termo.")
            else:
                try:
                    solicitar(settings, email, nome, inst, fin)
                    audit.registrar(settings, email, "publico", "solicitou_acesso")
                    st.success("Solicitação enviada. O administrador vai analisar.")
                except Exception:
                    st.error("Não foi possível registrar agora. Tente de novo em instantes.")


def painel_admin(c) -> None:
    """Página de administração: pendências, convite por e-mail e aprovação/revogação com validade."""
    s = c.settings
    try:
        df = listar(s)
    except Exception as e:
        st.error(f"Não foi possível ler a tabela de pesquisadores: {e}")
        return
    pend = df[df["status"] == "pendente"]
    st.subheader(f"Solicitações pendentes ({len(pend)})")
    if pend.empty:
        st.caption("Nenhuma solicitação aguardando análise.")
    else:
        st.dataframe(pend[["email", "nome", "instituicao", "finalidade", "termo_aceito_em"]], hide_index=True)

    a, b = st.columns(2)
    with a:
        st.subheader("Aprovar, recusar ou revogar")
        with st.form("form_decidir"):
            email = st.selectbox("Pessoa", df["email"].tolist() if len(df) else [], placeholder="Escolha")
            acao = st.radio("Decisão", ["Aprovar", "Recusar / revogar"], horizontal=True)
            validade = st.selectbox("Validade (ao aprovar)", list(VALIDADES))
            ok = st.form_submit_button("Salvar decisão", type="primary")
        if ok and email:
            novo = "aprovado" if acao == "Aprovar" else "revogado"
            decidir(s, email, novo, c.email or "admin", VALIDADES[validade] if novo == "aprovado" else None)
            audit.registrar(s, c.email, c.nivel, f"acesso_{novo}", email)
            st.success("Decisão registrada. Atualize a página para ver a lista nova.")
    with b:
        st.subheader("Convidar por e-mail")
        with st.form("form_convidar"):
            em = st.text_input("E-mail (conta Google da pessoa)")
            nm = st.text_input("Nome")
            val = st.selectbox("Validade", list(VALIDADES), index=1, key="val_convite")
            ok2 = st.form_submit_button("Autorizar como pesquisador", type="primary")
        if ok2:
            if "@" not in em:
                st.warning("Informe um e-mail válido.")
            else:
                convidar(s, em, nm, c.email or "admin", VALIDADES[val])
                audit.registrar(s, c.email, c.nivel, "acesso_convite", em.strip().lower())
                st.success("Pesquisador autorizado. Na próxima entrada com esse e-mail ele já terá acesso.")

    st.subheader("Todos os cadastros")
    mostrar = df.assign(status=df["status"].map(STATUS_ROTULO).fillna(df["status"]))
    st.dataframe(mostrar, hide_index=True)
