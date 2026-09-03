"""Etapa 4: siglas -> chaves, adjacencias por regra e propostas por corredor."""

from __future__ import annotations

import pandas as pd

from coff import cruzamento_pac as cp


def _siglas():
    return pd.DataFrame(
        {
            "sigla": ["CID", "QND", "SPA2"],
            "nome_pac": ["Ceará Mirim 2", "Queimada Nova 2", "Santa Vitória do Palmar 2"],
            "observacao": [None] * 3,
        }
    )


def test_chaves_das_siglas():
    t = cp.chaves_das_siglas(_siglas())
    assert list(t["pac_chave"]) == ["CEARA MIRIM 2", "QUEIMADA NOVA 2", "SANTA VITORIA DO PALMAR 2"]


def test_gerar_adjacencias_regras():
    chaves = {
        "CEARA MIRIM 2",
        "CEARA MIRIM 2 ICG",
        "SECC. LT CAMPINA GRANDE 3 – CEARA MIRIM 2",
        "QUEIMADA NOVA",
        "QUEIMADA NOVA 2",
        "SANTA VITORIA DO PALMAR 2",
        "OUTRA",
    }
    adj, faltantes = cp.gerar_adjacencias(chaves, _siglas())
    assert faltantes == []
    cid = adj[adj["sigla"] == "CID"]
    assert set(cid["relacao"]) == {"mesmo", "icg", "seccionamento"}
    assert "CEARA MIRIM 2 ICG" in set(cid["pac_adjacente"])
    qnd = adj[adj["sigla"] == "QND"]
    assert set(qnd["pac_adjacente"]) == {"QUEIMADA NOVA 2", "QUEIMADA NOVA"}
    assert "OUTRA" not in set(adj["pac_adjacente"])
    _, falt = cp.gerar_adjacencias({"X"}, _siglas())
    assert len(falt) == 3 and falt[0].startswith("CID = ")


def test_propor_adjacencias_por_corredor():
    desc = pd.DataFrame(
        {
            "elemento": [
                "LT 500 kV Açu III / Jaguaruana II",
                "FNESE",
                "LT 500 kV Campina Grande III / Ceará Mirim II",
            ],
            "eng_gwh": [3331.0, 1500.0, 72.2],
        }
    )
    chaves = {"ACU 3", "JAGUARUANA 2", "CEARA MIRIM 2", "CAMPINA GRANDE 3"}
    prop = cp.propor_adjacencias(desc, _siglas(), chaves)
    assert list(prop["sigla"]) == ["CID"] and prop.iloc[0]["pac_adjacente"] == "CAMPINA GRANDE 3"
    assert prop.iloc[0]["relacao"] == "corredor"
