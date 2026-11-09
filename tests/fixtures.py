"""Gera uma planilha SINTÉTICA com a mesma estrutura da planilha real (nomes e números inventados)."""
from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from mondo.loader import COLS_AVALIACAO

NOMES_FICTICIOS = []  # preenchido na geração: usado nos testes de vazamento


def _cpf_com_dv(base9: str) -> str:
    n = [int(c) for c in base9]
    d1 = (sum(n[i] * (10 - i) for i in range(9)) * 10 % 11) % 10
    n.append(d1)
    d2 = (sum(n[i] * (11 - i) for i in range(10)) * 10 % 11) % 10
    return base9 + str(d1) + str(d2)


def criar_planilha(caminho: Path, seed: int = 7) -> Path:
    rnd = random.Random(seed)
    wb = Workbook()

    # ---------------- Familias
    ws = wb.active
    ws.title = "Familias"
    ws.append(["ID", "RESPONSÁVEL", "ENDERECO", "NUMERO", "COMPLEMENTO", "Endereço Kobo", "COMUNIDADE",
               "BAIRRO", "ZONA", "LOCALIZAÇÂO", "LOCALIZAÇÂO"])
    comunidades = ["ALFA", "BETA", "GAMA", "DELTA"]
    zonas = ["URBANA", "RURAL", "RIBEIRINHA"]
    for fid in range(1, 21):
        com = comunidades[0] if fid <= 10 else comunidades[1] if fid <= 17 else comunidades[2 + fid % 2]
        loc = f"https://www.google.com/maps?q=-1.{40 + fid},-48.{50 + fid}" if fid % 4 else None
        ws.append([fid, f"Responsavel Ficticio {fid}", f"Rua Inventada {fid}", fid * 3, None, "Kobo " + str(fid),
                   com, f"Bairro {fid % 3}", zonas[fid % 3], loc, loc])

    # ---------------- Moradores
    wm = wb.create_sheet("Moradores")
    wm.append(["ID", "IDM", "Nome", "Sexo", "Nascimento", "Idade", "CPF", "Telefone", "Comunidade", "Zona",
               "Bairro", "Ciclo", "IPM", "Status", "Grupo"])
    n_mor = 0
    for fid in range(1, 22):  # família 21 não existe em Familias (órfã de propósito)
        for j in range(1, rnd.randint(3, 5) + 1):
            n_mor += 1
            nome = f"Pessoa Ficticia {fid}.{j}"
            NOMES_FICTICIOS.append(nome)
            nasc = datetime(rnd.choice([1950, 1975, 1990, 2005, 2012, 2018, 2022]), rnd.randint(1, 12), rnd.randint(1, 28))
            base = f"{rnd.randint(10_000_000, 99_999_999):08d}{rnd.randint(0, 9)}"
            cpf = _cpf_com_dv(base)
            r = rnd.random()
            cpf = cpf.lstrip("0") if cpf.startswith("0") else cpf
            if r < 0.25:
                cpf = "#N/A"
            elif r < 0.30:
                cpf = "111.111.111-11"
            wm.append([str(fid), f"{fid}.{j}", nome, rnd.choice(["Feminino", "Masculino"]), nasc, 40, cpf,
                       None if rnd.random() < .6 else "(91) 98888-7777", None, None, None, rnd.randint(1, 9),
                       rnd.choice([5, 15, 30, 50]), "Inativa" if rnd.random() < .05 else "Ativa", rnd.choice([1, 2])])
    wm.append(["1", "1.1", "Pessoa Ficticia 1.1", "Feminino", datetime(1990, 1, 1), 36, "#N/A", None, None, None,
               None, 9, 30, "Ativa", 1])  # IDM duplicado de propósito

    # ---------------- atividades
    wa = wb.create_sheet("atividades")
    wa.append(["ID", "IDM", "NOME", "COMUNIDADE", "DIMENSÃO", "Atividade + Turma", "ATIVIDADE", "INICIO", "FIM",
               "CATEGORIA", "TIPO", "TURMA", "DOAÇÃO", "CESTA BÁSICA"])
    ofertas = [
        ("SAÚDE", "ATENDIMENTO DE SAÚDE", "MUTIRÃO DE SAÚDE", "Oftalmologia", None, datetime(2025, 3, 1), datetime(2025, 3, 3), "ÓCULOS DE GRAU"),
        ("SAÚDE", "ATENDIMENTO DE SAÚDE", "MUTIRÃO DE SAÚDE", "OFTALMOLOGIA", None, datetime(2025, 3, 1), datetime(2025, 3, 3), None),
        ("SAÚDE", "ATENDIMENTO DE SAÚDE", "MUTIRÃO DE SAÚDE", "Pediatria", None, datetime(2025, 3, 1), datetime(2025, 3, 3), None),
        ("EDUCAÇÃO", "CURSO", "INFORMÁTICA BÁSICA", "Módulo 1", "Turma 1", datetime(2025, 6, 2), datetime(2025, 6, 30), "Kit de Formação (agenda e caneta)"),
        ("D.E.", "FORMAÇÃO", "EMPREENDEDORISMO", "Módulo 1", "TURMA 1", datetime(2026, 2, 2), datetime(2026, 2, 27), None),
        ("MEA", "OFICINA", "HORTA COMUNITÁRIA", "GERAL", None, datetime(2026, 4, 10), datetime(2026, 4, 10), "Kit quintais produtivos"),
    ]
    todos_idm = [f"{f}.{j}" for f in range(1, 22) for j in range(1, 4)]
    for dim, cat, atv, tipo, turma, ini, fim, doacao in ofertas:
        qtd = 1 if atv == "HORTA COMUNITÁRIA" else 12  # oferta pequena para testar a supressão (< k)
        for idm in rnd.sample(todos_idm, qtd):
            cesta = "sim" if rnd.random() < .2 else None
            linha = [None, idm, f"Pessoa Ficticia {idm}", "ALFA", dim, f"{atv} {turma or ''}".strip(), atv, ini, fim,
                     cat, tipo, turma, doacao if rnd.random() < .7 else "Sim", cesta]
            wa.append(linha)
            if rnd.random() < .15:
                wa.append(linha)  # duplicata exata
        wa.append([None, None, f"Visitante Externo {tipo}", None, dim, f"{atv} {turma or ''}".strip(), atv, ini, fim,
                   cat, tipo, turma, None, None])
        wa.append([None, "99.1", "Pessoa Fora do Cadastro", None, dim, f"{atv} {turma or ''}".strip(), atv, ini, fim,
                   cat, tipo, turma, None, None])

    # ---------------- avaliação
    wv = wb.create_sheet("avaliação")
    wv.append(COLS_AVALIACAO)
    for i in range(40):
        idm = rnd.choice(todos_idm + [None, None, "98.1"])
        wv.append([rnd.choice(["SAÚDE", "MEA", "RENDA", "EDUCAÇÃO"]), rnd.choice(["Formação A", "Oficina B", "Curso C"]),
                   rnd.choice([datetime(2025, 5, 10), "maio de 2026", "12/06/2025", None]), idm and f"Pessoa Ficticia {idm}", idm,
                   5, 4, rnd.choice([5, "5", 4]), rnd.choice([5, "4"]), 5, 4, 5, None if i % 2 else 5, None,
                   "Tarde", 0, 1, 0, 0, "Interesse pessoal", 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, "n/r",
                   "Texto livre com nome Pessoa Ficticia 1.1", "Sugestão livre", rnd.choice([4.5, "4,8", 5]),
                   "Formação", "Conteúdo", "Tempo"])

    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb.save(caminho)
    return caminho
