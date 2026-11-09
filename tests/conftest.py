import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.fixtures import criar_planilha  # noqa: E402


@pytest.fixture(scope="session")
def planilha(tmp_path_factory) -> Path:
    return criar_planilha(tmp_path_factory.mktemp("dados") / "sintetica.xlsx")


@pytest.fixture(scope="session")
def modelo(planilha):
    from mondo.loader import construir_modelo, ler_planilha
    return construir_modelo(ler_planilha(planilha))
