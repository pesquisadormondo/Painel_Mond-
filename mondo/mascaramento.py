"""Ambiente de TESTE: troca identificações por dados fictícios, mantendo ids, datas e todos os números agregados.

O que muda: nomes, CPF, telefone, endereço, complemento, coordenadas (deslocadas ~1 km), nome do responsável e do
avaliador, textos livres e dados de local/foto/documentação das ofertas.
O que NÃO muda: códigos, sexo, ciclo, IPM, status, comunidade, bairro, zona, atividades, participações, notas.
Mesmo assim, comunidade + idade + atividades de saúde continuam sendo informações sensíveis combinadas:
use o ambiente de teste só com pessoas do projeto.
"""
from __future__ import annotations

import hashlib
from datetime import date

import numpy as np
import pandas as pd

from .privacy import faixa_etaria, idade_em

TEXTO_REMOVIDO = "[texto removido no ambiente de teste]"


def _h(semente: str, chave) -> int:
    return int(hashlib.sha256(f"{semente}:{chave}".encode("utf-8")).hexdigest()[:12], 16)


def _cpf_ficticio(n: int) -> str:
    d = [int(c) for c in f"{n % 10**9:09d}"]
    for tam in (9, 10):
        d.append((sum(d[i] * (tam + 1 - i) for i in range(tam)) * 10 % 11) % 10)
    return "".join(map(str, d))


def _obj(valores, indice) -> pd.Series:
    return pd.Series(list(valores), index=indice, dtype=object)


def mascarar(frames: dict[str, pd.DataFrame], semente: str = "mondo-teste", ref: date | None = None) -> dict[str, pd.DataFrame]:
    ref = ref or date.today()
    f = {k: v.copy() for k, v in frames.items()}

    # ---------------- moradores
    m = f["morador"]
    cod = m["codigo_morador"].astype(str)
    m["nome"] = _obj((f"Pessoa Fictícia {c}" for c in cod), m.index)
    m["cpf"] = _obj((None if pd.isna(v) else _cpf_ficticio(_h(semente, f"cpf{i}"))
                     for i, v in zip(m["id_morador"], m["cpf"])), m.index)
    m["telefone"] = _obj((None if pd.isna(v) else "9" + f"{_h(semente, f'tel{i}') % 10**8:08d}"
                          for i, v in zip(m["id_morador"], m["telefone"])), m.index)
    nasc = pd.to_datetime(m["data_nascimento"], errors="coerce")
    desloc = pd.to_timedelta([(_h(semente, f"nasc{i}") % 91) - 45 for i in m["id_morador"]], unit="D")
    novo = nasc + desloc
    mesma_faixa = faixa_etaria(idade_em(novo, ref)).fillna("") == faixa_etaria(idade_em(nasc, ref)).fillna("")
    m["data_nascimento"] = novo.where(mesma_faixa, nasc)  # a faixa etária nunca muda

    # ---------------- famílias
    fam = f["familia"]
    fam["responsavel_nome"] = _obj((f"Responsável Fictício {i}" for i in fam["id_familia"]), fam.index)
    fam["endereco"] = _obj((f"Rua Fictícia {i}" for i in fam["id_familia"]), fam.index)
    fam["numero"] = _obj((str(i) for i in fam["id_familia"]), fam.index)
    fam["complemento"] = None
    fam["endereco_kobo"] = None
    for col, tag in (("latitude", "lat"), ("longitude", "lon")):
        v = pd.to_numeric(fam[col], errors="coerce")
        d = pd.Series([((_h(semente, f"{tag}{i}") % 2001) - 1000) / 100_000 for i in fam["id_familia"]], index=fam.index)
        fam[col] = (v + d).round(6)

    # ---------------- participantes
    p = f["participante"]
    nome_mor = dict(zip(m["id_morador"], m["nome"]))
    p["nome"] = _obj((nome_mor.get(im) if not pd.isna(im) else f"Participante Externo {ip}"
                      for ip, im in zip(p["id_participante"], p["id_morador"])), p.index)

    # ---------------- avaliações e ofertas
    av = f["avaliacao"]
    av["nome_avaliador"] = _obj((None if pd.isna(v) else f"Avaliador Fictício {i}"
                                 for i, v in zip(av["id_avaliacao"], av["nome_avaliador"])), av.index)
    for col in ("outro_texto", "elogios_texto", "melhorias_texto"):
        av[col] = _obj((None if pd.isna(v) else TEXTO_REMOVIDO for v in av[col]), av.index)
    of = f["oferta"]
    for col in ("local", "descricao", "foto_coletiva", "link_documentacao"):
        of[col] = None
    return f
