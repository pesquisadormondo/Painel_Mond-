"""Monta o pacote de download do pesquisador: CSVs pseudonimizados, dicionário de dados e LEIA-ME."""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime

import pandas as pd

from .metrics import avaliacao_enriquecida, fato_participacao, morador_enriquecido
from .privacy import aplicar_k_anonimato, passos_padrao

DESCRICOES = {
    "id_morador": "Código pseudônimo do morador (HMAC). Liga os arquivos; não permite identificar a pessoa.",
    "id_familia": "Código pseudônimo da família (HMAC).",
    "id_participante": "Código pseudônimo do participante (morador do cadastro ou pessoa externa).",
    "id_avaliacao": "Número sequencial da resposta de avaliação.",
    "id_participacao": "Número sequencial da participação.",
    "id_oferta": "Código da oferta (turma/edição de uma atividade).",
    "sexo": "Sexo do morador (feminino, masculino, outro/não declarou). Vazio = generalizado por privacidade.",
    "faixa_etaria": "Faixa de idade na data da geração (0–5, 6–11, 12–17, 18–29, 30–44, 45–59, 60+; '0–17'/'18+' se generalizada).",
    "comunidade": "Comunidade de residência da família ('Outras' = agrupada por privacidade).",
    "zona": "Zona de residência (urbana, rural, ribeirinha, periurbana). Vazio = generalizado.",
    "ciclo": "Ciclo do morador (1 a 9). Significado a confirmar com o Instituto.",
    "ipm": "IPM do morador (significado a confirmar com o Instituto).",
    "status": "Situação do morador (Ativa/Inativa).",
    "grupo": "Grupo do morador (1 ou 2). Significado a confirmar.",
    "n_moradores_familia": "Número de moradores da família (limitado a 8).",
    "origem": "'cadastro' = morador cadastrado; 'externo' = pessoa que só consta nas atividades.",
    "atividade": "Nome da atividade.", "dimensao": "Dimensão da atividade ou da avaliação.",
    "categoria": "Categoria da atividade.", "turma": "Turma/fase/lote da oferta (rótulo da planilha).",
    "tipo": "Módulo ou especialidade da participação.",
    "data_inicio": "Início da oferta (AAAA-MM-DD).", "data_fim": "Fim da oferta (AAAA-MM-DD).",
    "doacao": "Recebeu doação (verdadeiro/falso).", "item_doacao": "Item de doação recebido, quando informado.",
    "cesta_basica": "Recebeu cesta básica (verdadeiro/falso).",
    "comunidade_atividade": "Comunidade informada na linha da atividade (significado a confirmar).",
    "evento": "Formação ou evento avaliado.", "data_formacao": "Data da formação, quando interpretável.",
    "q01_aprendizado": "Nota: aprendizado.", "q02_organizacao": "Nota: organização.",
    "q03_professores": "Nota: professores.", "q04_recomendacao": "Nota: recomendaria.",
    "q05_infraestrutura": "Nota: infraestrutura.", "q06_duracao": "Nota: duração.",
    "q07_informacoes_previas": "Nota: informações prévias.", "q08_material": "Nota: material.",
    "turno_manha": "Prefere turno da manhã.", "turno_tarde": "Prefere turno da tarde.",
    "turno_noite": "Prefere turno da noite.", "turno_fim_semana": "Prefere fim de semana.",
    "nota_geral": "Nota geral da formação.", "formato": "Formato (curso, formação, oficina).",
    "categoria_elogios": "Categoria do elogio (classificação da equipe).",
    "categoria_melhorias": "Categoria da sugestão de melhoria (classificação da equipe).",
}
for _c, _t in {"int_trabalhar_area": "Trabalhar na área", "int_primeiro_emprego": "Conseguir o primeiro emprego",
               "int_mudar_area": "Mudar de área", "int_crescer_carreira": "Crescer na carreira",
               "int_abrir_negocio": "Abrir o próprio negócio", "int_renda_extra": "Aumentar a renda",
               "int_interesse_pessoal": "Aprender por interesse pessoal", "int_feiras_eventos": "Participar de feiras e eventos",
               "int_indeciso": "Ainda não sabe", "int_outro": "Outra intenção"}.items():
    DESCRICOES[_c] = f"Intenção após a formação: {_t} (verdadeiro/falso)."

COLS_MORADORES = ["id_morador", "id_familia", "sexo", "faixa_etaria", "comunidade", "zona", "ciclo", "ipm",
                  "status", "grupo", "n_moradores_familia"]
COLS_PARTICIPACOES = ["id_participacao", "id_participante", "id_morador", "origem", "atividade", "dimensao",
                      "categoria", "turma", "tipo", "data_inicio", "data_fim", "doacao", "item_doacao",
                      "cesta_basica", "comunidade_atividade"]
COLS_AVALIACOES = (["id_avaliacao", "id_participante", "id_morador", "dimensao", "evento", "data_formacao"]
                   + ["q01_aprendizado", "q02_organizacao", "q03_professores", "q04_recomendacao",
                      "q05_infraestrutura", "q06_duracao", "q07_informacoes_previas", "q08_material"]
                   + ["turno_manha", "turno_tarde", "turno_noite", "turno_fim_semana"]
                   + ["int_trabalhar_area", "int_primeiro_emprego", "int_mudar_area", "int_crescer_carreira",
                      "int_abrir_negocio", "int_renda_extra", "int_interesse_pessoal", "int_feiras_eventos",
                      "int_indeciso", "int_outro"]
                   + ["nota_geral", "formato", "categoria_elogios", "categoria_melhorias"])

LEIA_ME = """PACOTE DE DADOS PSEUDONIMIZADOS - INSTITUTO MONDÓ
Gerado em: {gerado}   |   Referência de idade: {ref}   |   Gerado para: {usuario}

CONTEÚDO
- moradores_pseudonimizados.csv   : perfil dos moradores (uma linha por morador)
- participacoes_pseudonimizadas.csv: participações em ofertas (liga a moradores por id_morador)
- avaliacoes_pseudonimizadas.csv  : respostas de avaliação, sem textos livres
- dicionario_de_dados.csv         : descrição de cada coluna

PROTEÇÕES APLICADAS
- Removidos: nomes, CPF, telefone, endereços, coordenadas, nome de responsável/avaliador e textos livres.
- Identificadores substituídos por códigos pseudônimos (HMAC-SHA256). O mesmo código aparece nos arquivos
  e em novas versões do conjunto, o que permite análise longitudinal sem revelar a pessoa.
- Data de nascimento substituída por faixa etária.
- k-anonimato (k = {k}) em moradores_pseudonimizados.csv: cada combinação de comunidade, faixa etária, sexo e zona
  tem ao menos {k} moradores. Onde isso não ocorria, valores foram agrupados ('Outras') ou apagados (vazio).
  Linhas alteradas: {alteradas} de {linhas}.

ATENÇÃO
- Dados pseudonimizados continuam sendo dados pessoais (LGPD, art. 13, §4º). Use somente para a finalidade
  aprovada, não tente reidentificar pessoas, não compartilhe os arquivos e descarte-os ao fim do prazo.
- Participações combinam atividade, datas e tipo (inclui atendimentos de saúde): não cruze com outras bases
  para identificar indivíduos.
- Os valores de ciclo, ipm e grupo seguem a planilha; seus significados estão em validação com o Instituto.
"""


def _dicionario(arquivos: dict[str, pd.DataFrame]) -> pd.DataFrame:
    linhas = []
    for nome, df in arquivos.items():
        for c in df.columns:
            linhas.append({"arquivo": nome, "coluna": c, "tipo": str(df[c].dtype), "descricao": DESCRICOES.get(c, "")})
    return pd.DataFrame(linhas)


def montar_pacote(f_pesq: dict[str, pd.DataFrame], ref: date, k: int, usuario: str):
    """Devolve (bytes_do_zip, resumo). `f_pesq` deve ser o resultado de privacy.para_pesquisa()."""
    mor = morador_enriquecido(f_pesq, ref)
    fato = fato_participacao(f_pesq, mor)
    av = avaliacao_enriquecida(f_pesq)

    moradores, rel = aplicar_k_anonimato(
        mor[COLS_MORADORES], ["comunidade", "faixa_etaria", "sexo", "zona"], k, passos_padrao())
    participacoes = fato[COLS_PARTICIPACOES]
    part = f_pesq["participante"][["id_participante", "id_morador"]]
    avaliacoes = av.merge(part, on="id_participante", how="left", suffixes=("", "_p"))
    if "id_morador" not in avaliacoes.columns:
        avaliacoes["id_morador"] = None
    avaliacoes = avaliacoes[COLS_AVALIACOES]

    arquivos = {
        "moradores_pseudonimizados.csv": moradores,
        "participacoes_pseudonimizadas.csv": participacoes,
        "avaliacoes_pseudonimizadas.csv": avaliacoes,
    }
    arquivos["dicionario_de_dados.csv"] = _dicionario(dict(arquivos))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, df in arquivos.items():
            z.writestr(nome, df.to_csv(index=False, date_format="%Y-%m-%d"))
        z.writestr("LEIA-ME.txt", LEIA_ME.format(
            gerado=datetime.now().strftime("%d/%m/%Y %H:%M"), ref=ref.strftime("%d/%m/%Y"), usuario=usuario, k=k,
            alteradas=rel["linhas_alteradas"], linhas=rel["linhas"]))
    resumo = pd.DataFrame([{"arquivo": n, "linhas": len(d), "colunas": d.shape[1]} for n, d in arquivos.items()])
    return buf.getvalue(), resumo, rel
