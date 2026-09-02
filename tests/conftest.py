"""Fixtures sinteticas (spec v2, secao 6). Valores pequenos, calculados a mao nos testes."""

from __future__ import annotations

import pandas as pd
import pytest

COLUNAS = [
    "id_subsistema",
    "nom_subsistema",
    "id_estado",
    "nom_estado",
    "nom_usina",
    "id_ons",
    "ceg",
    "din_instante",
    "val_geracao",
    "val_geracaolimitada",
    "val_disponibilidade",
    "val_geracaoreferencia",
    "val_geracaoreferenciafinal",
    "cod_razaorestricao",
    "cod_origemrestricao",
    "dsc_restricao",
]


def _linha(instante, ger, lim, disp, ref, reffinal, cod, orig, dsc, usina="USI_A"):
    return [
        "NE",
        "NORDESTE",
        "BA",
        "BAHIA",
        f"CONJ. {usina}",
        usina,
        "-",
        instante,
        ger,
        lim,
        disp,
        ref,
        reffinal,
        cod,
        orig,
        dsc,
    ]


@pytest.fixture
def df_usina_8_instantes() -> pd.DataFrame:
    """1 usina x 8 instantes de 30 min cobrindo os casos da secao 6 da spec.

    ordem: (0) sem restricao; (1) ENE ger<ref; (2) REL final<ref; (3) ENE ger>=ref;
    (4) CNF limite=0; (5) codigo desconhecido; (6) instante duplicado de (1);
    (7) geracao negativa com ENE.
    """
    linhas = [
        _linha("2025-01-01 00:00:00", 10.0, None, 50.0, 12.0, None, None, None, None),
        _linha(
            "2025-01-01 00:30:00",
            10.0,
            10.0,
            50.0,
            30.0,
            None,
            "ENE",
            "SIS",
            "Controle de frequencia",
        ),
        _linha(
            "2025-01-01 01:00:00",
            10.0,
            10.0,
            50.0,
            30.0,
            20.0,
            "REL",
            "LOC",
            "Indisponibilidade LT",
        ),
        _linha(
            "2025-01-01 01:30:00",
            30.0,
            30.0,
            50.0,
            25.0,
            None,
            "ENE",
            "SIS",
            "Controle de frequencia",
        ),
        _linha("2025-01-01 02:00:00", 0.0, 0.0, 50.0, 40.0, None, "CNF", "LOC", "Inequacao X"),
        _linha("2025-01-01 02:30:00", 5.0, 5.0, 50.0, 15.0, None, "XYZ", "LOC", "Codigo estranho"),
        _linha(
            "2025-01-01 00:30:00",
            11.0,
            10.0,
            50.0,
            31.0,
            None,
            "ENE",
            "SIS",
            "Controle de frequencia",
        ),
        _linha(
            "2025-01-01 03:00:00",
            -2.0,
            0.0,
            50.0,
            8.0,
            None,
            "ENE",
            "SIS",
            "Controle de frequencia",
        ),
    ]
    df = pd.DataFrame(linhas, columns=COLUNAS)
    df["fonte"] = "EOL"
    df["periodo"] = "2025_01"
    return df


@pytest.fixture
def df_mes_2_usinas() -> pd.DataFrame:
    """Mes sintetico minimo: 2 usinas x 4 instantes, para as agregacoes."""
    linhas = []
    for h, (ga, ra, ca) in enumerate(
        [(10.0, 20.0, "ENE"), (10.0, 10.0, None), (0.0, 30.0, "CNF"), (5.0, 25.0, "REL")]
    ):
        linhas.append(
            _linha(
                f"2025-02-01 0{h}:00:00",
                ga,
                None if ca is None else ga,
                50.0,
                ra,
                ra - 5 if ca == "REL" else None,
                ca,
                None if ca is None else "SIS",
                ca,
                "USI_A",
            )
        )
        linhas.append(
            _linha(f"2025-02-01 0{h}:00:00", 2.0, None, 10.0, 2.0, None, None, None, None, "USI_B")
        )
    df = pd.DataFrame(linhas, columns=COLUNAS)
    df["fonte"] = "UFV"
    df["periodo"] = "2025_02"
    return df
