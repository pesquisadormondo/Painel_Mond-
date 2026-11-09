"""Monta um Ctx (contexto de nível) a partir de uma planilha, para testar páginas isoladamente."""
import functools
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from mondo import loader
from mondo.metrics import avaliacao_enriquecida, fato_participacao, morador_enriquecido
from mondo.privacy import para_pesquisa
from mondo.ui import Ctx, aplicar_filtros


@functools.lru_cache(maxsize=None)
def _modelo(xlsx: str):
    return loader.construir_modelo(loader.ler_planilha(Path(xlsx)))


def construir_ctx(nivel: str, xlsx: str, log: str, k: int = 5, segredo: str = "segredo-de-teste") -> Ctx:
    ref = date(2026, 11, 4)
    frames, quali = _modelo(xlsx)
    fr = frames if nivel == "admin" else para_pesquisa(frames, segredo, ref)
    mor = morador_enriquecido(fr, ref)
    fato_total = fato_participacao(fr, mor)
    fato, filtros = aplicar_filtros(fato_total)
    settings = SimpleNamespace(k_min=k, pseudo_secret=segredo, log_path=Path(log), ref_date=ref, backend="xlsx")
    return Ctx(nivel=nivel, k=k, ref=ref, settings=settings, email="teste@local", frames=fr, mor=mor,
               fato_total=fato_total, fato=fato, av=avaliacao_enriquecida(fr), qualidade=quali,
               carregado_em="agora", filtros=filtros)
