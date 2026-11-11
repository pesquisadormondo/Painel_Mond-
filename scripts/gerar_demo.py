"""Gera demo/dados_demo.xlsx: planilha 100% FICTÍCIA, com a mesma estrutura da planilha real.

Uso:  python scripts/gerar_demo.py
Serve para demonstrar o painel e coletar feedback sem expor dados pessoais. Nomes, CPFs e telefones são inventados.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mondo.loader import COLS_AVALIACAO  # noqa: E402

rnd = random.Random(2026)


def cpf_fake() -> str:
    base = [rnd.randint(0, 9) for _ in range(9)]
    for n in (9, 10):
        base.append((sum(base[i] * (n + 1 - i) for i in range(n)) * 10 % 11) % 10)
    return "".join(map(str, base))


COMUNIDADES = ["Comunidade Aurora", "Vila Esperança", "Beira do Rio", "Alto da Serra", "Recanto Verde", "Porto Novo",
               "Campo Limpo", "São Lucas", "Ilha Grande", "Nova Aliança", "Sítio Boa Vista", "Travessa do Meio"]
ZONAS = ["URBANA", "RURAL", "RIBEIRINHA", "PERIURBANA"]
wb = Workbook()

# ---------------- Familias
ws = wb.active
ws.title = "Familias"
ws.append(["ID", "RESPONSÁVEL", "ENDERECO", "NUMERO", "COMPLEMENTO", "Endereço Kobo", "COMUNIDADE", "BAIRRO",
           "ZONA", "LOCALIZAÇÂO", "LOCALIZAÇÂO"])
N_FAM = 320
pesos_com = [20, 14, 8, 6, 12, 8, 7, 6, 5, 6, 5, 3]
fam_com = {}
for fid in range(1, N_FAM + 1):
    com = rnd.choices(COMUNIDADES, pesos_com)[0]
    fam_com[fid] = com
    z = ZONAS[COMUNIDADES.index(com) % 4]
    lat, lon = -1.40 - rnd.random() * 0.4, -48.30 - rnd.random() * 0.5
    loc = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}" if rnd.random() < .88 else None
    ws.append([fid, f"Responsavel Ficticio {fid}", f"Rua Ficticia {fid}", fid, None, f"Kobo {fid}", com,
               f"Bairro {rnd.randint(1, 18)}", z, loc, loc])

# ---------------- Moradores
wm = wb.create_sheet("Moradores")
wm.append(["ID", "IDM", "Nome", "Sexo", "Nascimento", "Idade", "CPF", "Telefone", "Comunidade", "Zona", "Bairro",
           "Ciclo", "IPM", "Status", "Grupo"])
moradores = []
for fid in range(1, N_FAM + 1):
    for j in range(1, rnd.randint(2, 7) + 1):
        faixa = rnd.choices([(0, 17), (18, 59), (60, 90)], [46, 44, 10])[0]
        nasc = datetime(2026, 11, 4) - timedelta(days=int(365.25 * rnd.uniform(*faixa)))
        idm = f"{fid}.{j}"
        moradores.append(idm)
        cpf = cpf_fake() if rnd.random() < .45 else "#N/A"
        wm.append([str(fid), idm, f"Pessoa Ficticia {idm}", rnd.choice(["Feminino", "Masculino"]), nasc, 0, cpf,
                   "(91) 9" + "".join(str(rnd.randint(0, 9)) for _ in range(8)) if rnd.random() < .25 else "#N/A",
                   None, None, None, rnd.choices(range(1, 10), [3, 3, 3, 3, 3, 3, 3, 3, 77])[0],
                   rnd.choice([5, 15, 20, 30, 40, 50, 60]), "Inativa" if rnd.random() < .03 else "Ativa", rnd.choice([1, 2])])

# ---------------- atividades
wa = wb.create_sheet("atividades")
wa.append(["ID", "IDM", "NOME", "COMUNIDADE", "DIMENSÃO", "Atividade + Turma", "ATIVIDADE", "INICIO", "FIM", "CATEGORIA",
           "TIPO", "TURMA", "DOAÇÃO", "CESTA BÁSICA"])
CATALOGO = [  # dimensão, categoria, atividade, tipos, turmas, ofertas, participantes por oferta, doação
    ("SAÚDE", "ATENDIMENTO DE SAÚDE", "MUTIRÃO DE SAÚDE", ["Oftalmologia", "Clínico geral", "Pediatria", "Ginecologia",
                                                              "Odontologia", "Testes rápidos"], [None], 8, (25, 70), None),
    ("SAÚDE", "DOAÇÃO", "ENTREGA DE ÓCULOS", ["Oftalmologia"], [None], 5, (15, 40), "Óculos de grau"),
    ("EDUCAÇÃO", "CURSO", "INFORMÁTICA BÁSICA", ["Módulo 1", "Módulo 2", "Módulo 3", "Módulo 4"], ["Turma 1", "Turma 2", "Turma 3"], 3, (15, 30), "Kit de formação (agenda e caneta)"),
    ("D.E.", "FORMAÇÃO", "EMPREENDEDORISMO", ["Módulo 1", "Módulo 2"], ["Turma 1", "Turma 2"], 4, (20, 45), "Kit de formação (ecobag, agenda e caneta)"),
    ("D.E.", "FORMAÇÃO", "FINANÇAS PESSOAIS", ["GERAL"], [None], 5, (15, 40), None),
    ("D.E.", "ATENDIMENTO", "MENTORIA", ["GERAL"], [None], 4, (10, 25), None),
    ("MEA", "OFICINA", "HORTA COMUNITÁRIA", ["GERAL"], [None], 5, (12, 30), "Kit quintais produtivos"),
    ("MEA", "OFICINA", "EDUCAÇÃO AMBIENTAL", ["GERAL"], [None], 4, (15, 40), "Kit de higiene bucal"),
    ("ACOMPANHAMENTO FAMILIAR", "ATENDIMENTO", "VISITA FAMILIAR", ["GERAL"], [None], 2, (8, 14), None),
    ("EDUCAÇÃO", "OFICINA", "OFICINA DE LIBRAS", ["GERAL"], [None], 1, (3, 3), None),  # grupo pequeno: mostra a supressão
]
ENGAJADOS = rnd.sample(moradores, int(len(moradores) * 0.62))  # nem todo morador participa de atividades
for dim, cat, atv, tipos, turmas, n_of, (lo, hi), doacao in CATALOGO:
    for _ in range(n_of):
        ini = datetime(2024, 2, 5) + timedelta(days=rnd.randint(0, 900))
        fim = ini + timedelta(days=rnd.choice([0, 1, 2, 14, 28]))
        turma = rnd.choice(turmas)
        for tipo in tipos:
            for idm in rnd.sample(ENGAJADOS, rnd.randint(lo, hi)):
                linha = [None, idm, f"Pessoa Ficticia {idm}", rnd.choice(COMUNIDADES), dim, f"{atv} {turma or ''}".strip(), atv,
                         ini, fim, cat, tipo, turma, doacao if doacao and rnd.random() < .8 else None,
                         "sim" if rnd.random() < .12 else None]
                wa.append(linha)
                if rnd.random() < .06:
                    wa.append(linha)
            for k in range(0 if atv == "OFICINA DE LIBRAS" else rnd.randint(0, 3)):  # participantes externos (só nome)
                wa.append([None, None, f"Visitante Ficticio {rnd.randint(1, 400)}", None, dim, f"{atv} {turma or ''}".strip(),
                           atv, ini, fim, cat, tipo, turma, None, None])

# ---------------- avaliação
wv = wb.create_sheet("avaliação")
wv.append(COLS_AVALIACAO)
EVENTOS = [("SAÚDE", "Mutirão de Saúde"), ("EDUCAÇÃO", "Informática Básica"), ("RENDA", "Empreendedorismo"),
           ("RENDA", "Finanças Pessoais"), ("MEA", "Horta Comunitária"), ("MEA", "Educação Ambiental"),
           ("NUTRIÇÃO", "Oficina de Alimentação")]
for _ in range(520):
    dim, ev = rnd.choice(EVENTOS)
    idm = rnd.choice(moradores) if rnd.random() < .45 else None
    nota = lambda: rnd.choices([3, 4, 5], [1, 3, 8])[0]
    intencoes = [1 if rnd.random() < p else 0 for p in (.3, .15, .08, .25, .35, .4, .3, .12, .1, .02)]
    turno = [1 if rnd.random() < p else 0 for p in (.4, .3, .15, .25)]
    wv.append([dim, ev, rnd.choice([datetime(2025, 5, 10), datetime(2026, 3, 14), "maio de 2026", None]),
               f"Pessoa Ficticia {idm}" if idm else None, idm, nota(), nota(), nota(), nota(), nota(), nota(), nota(),
               nota() if rnd.random() < .56 else None, None, "Tarde", *turno, "Interesse pessoal", *intencoes, "n/r",
               "Comentário fictício", "Sugestão fictícia", round(rnd.uniform(4, 5), 2), "Formação", "Conteúdo", "Tempo"])

saida = ROOT / "demo" / "dados_demo.xlsx"
saida.parent.mkdir(exist_ok=True)
wb.save(saida)
print("Planilha fictícia gerada:", saida)
