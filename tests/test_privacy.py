from datetime import date

import numpy as np
import pandas as pd

from mondo import privacy
from mondo.loader import cpf_valido


def test_suprimir_primaria_e_complementar():
    df = pd.DataFrame({"g": list("abcd"), "valor": [3, 40, 20, 7]})
    out = privacy.suprimir(df, "valor", k=5)
    assert out["suprimido"].tolist() == [True, False, False, True]  # 'a' (<5) + menor restante ('d')
    assert out["valor"].isna().tolist() == [True, False, False, True]


def test_suprimir_sem_complementar_e_zero_nao_conta():
    df = pd.DataFrame({"g": list("abc"), "valor": [0, 3, 50]})
    out = privacy.suprimir(df, "valor", k=5, complementar=False)
    assert out["suprimido"].tolist() == [False, True, False]


def test_pseudonimo_estavel_e_separado_por_prefixo():
    s = pd.Series([1, 2, 2, None])
    a = privacy.pseudonimizar(s, "segredo", "m")
    b = privacy.pseudonimizar(s, "segredo", "p")
    c = privacy.pseudonimizar(s, "outro", "m")
    assert a[1] == a[2] and a[0] != a[1] and pd.isna(a[3])
    assert a[0] != b[0] and a[0] != c[0] and len(a[0]) == 12
    assert privacy.pseudonimizar(pd.Series([1.0]), "segredo", "m")[0] == a[0]  # 1 e 1.0 dão o mesmo código


def test_idade_e_faixa():
    nasc = pd.Series(pd.to_datetime(["2000-11-04", "2000-11-05", "2026-01-01", None]))
    idade = privacy.idade_em(nasc, date(2026, 11, 4))
    assert idade.iloc[:3].tolist() == [26, 25, 0] and np.isnan(idade.iloc[3])
    assert privacy.faixa_etaria(idade).tolist() == ["18–29", "18–29", "0–5", None]


def test_k_anonimato_garante_grupos_minimos():
    rnd = np.random.default_rng(0)
    df = pd.DataFrame({
        "comunidade": rnd.choice(["A", "B", "C", "RARA"], 300, p=[.4, .3, .29, .01]),
        "faixa_etaria": rnd.choice(privacy.AGE_LABELS, 300),
        "sexo": rnd.choice(["F", "M"], 300), "zona": rnd.choice(["U", "R"], 300)})
    qi = ["comunidade", "faixa_etaria", "sexo", "zona"]
    out, rel = privacy.aplicar_k_anonimato(df, qi, k=5)
    conhecidos = out[out[qi].notna().any(axis=1)]
    assert conhecidos.groupby(qi, dropna=False).size().min() >= 5
    assert rel["menor_grupo_antes"] < 5 <= rel["menor_grupo_depois"]
    assert "RARA" not in set(out["comunidade"].dropna())


def test_cpf_valido():
    assert cpf_valido("52998224725") and not cpf_valido("52998224726") and not cpf_valido("11111111111")
    assert not cpf_valido(None)
