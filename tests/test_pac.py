"""Mapa usina -> PAC: normalizacao de nomes, rateio por potencia e casos sem casamento."""

from __future__ import annotations

import pandas as pd
import pytest

from coff import pac


def test_normalizar_pac():
    assert pac.normalizar_pac("SE ACU III 500,0 kV") == ("ACU 3", 500.0)
    assert pac.normalizar_pac("SE Açu III 500 kV") == ("ACU 3", 500.0)
    assert pac.normalizar_pac("SE 500 KV ARINOS 2") == pac.normalizar_pac("SE Arinos II 500 kV")
    assert pac.normalizar_pac("Rede de Distribuição 13,8 kV") == ("REDE DE DISTRIBUICAO", 13.8)
    assert pac.normalizar_pac(None) == (None, None) and pac.normalizar_pac("  ") == (None, None)


def _cadastro():
    modalidade = pd.DataFrame(
        {
            "ceg": ["A1", "A2", "A3", "B1", "C1"],
            "nom_pontoconexao": [
                "SE X 500 kV",
                "SE X 500,0 KV",
                "SE Y 230 kV",
                "SE Z 230 kV",
                None,
            ],
            "val_potenciaautorizada": [60.0, 30.0, 10.0, 50.0, 20.0],
        }
    )
    conjuntos = pd.DataFrame(
        {
            "id_ons_conjunto": ["CJU_A", "CJU_A", "CJU_A", "CJU_D", "CJU_D"],
            "ceg": ["A1", "A2", "A3", "A1", "A3"],
            "dat_fimrelacionamento": [None, None, None, None, "2024-01-01"],
        }
    )
    return modalidade, conjuntos


def test_construir_mapa_regras():
    modalidade, conjuntos = _cadastro()
    usinas = pd.DataFrame(
        {
            "id_ons": ["CJU_A", "CJU_D", "IND_B", "IND_C", "CJU_Z"],
            "nom_usina": ["Conj A", "Conj D", "Usina B", "Usina C", "Conj Z"],
            "uf": ["BA"] * 5,
            "fonte": ["EOL"] * 5,
            "ceg": ["-", "-", "B1", "C1", "-"],
        }
    )
    mapa = pac.construir_mapa(usinas, modalidade, conjuntos)
    a = mapa[mapa["id_ons"] == "CJU_A"]
    assert a["metodo"].unique().tolist() == ["ons_cadastro"] and a["confianca"].iloc[0] == "alta"
    assert a["pac_nome"].iloc[0] == "X" and a["fracao_potencia"].iloc[0] == 1.0  # 90 MW de 100
    d = mapa[mapa["id_ons"] == "CJU_D"]  # A3 saiu do conjunto -> so A1 (X)
    assert len(d) == 1 and d["pac_nome"].iloc[0] == "X"
    b = mapa[mapa["id_ons"] == "IND_B"].iloc[0]
    assert b["pac_nome"] == "Z" and b["metodo"] == "ons_cadastro" and b["pot_mw"] == 50.0
    c = mapa[mapa["id_ons"] == "IND_C"].iloc[0]  # ceg existe mas sem ponto de conexao
    assert c["metodo"] == "nao_casado" and pd.isna(c["pac_nome"])
    z = mapa[mapa["id_ons"] == "CJU_Z"].iloc[0]
    assert z["metodo"] == "nao_casado"
    assert mapa[mapa["id_ons"] == "CJU_A"]["vigencia"].iloc[0] == "ativo"


def test_conjunto_encerrado_usa_ultima_composicao():
    modalidade = pd.DataFrame(
        {
            "ceg": ["A1", "A2"],
            "nom_pontoconexao": ["SE X 500 kV", "SE Y 230 kV"],
            "val_potenciaautorizada": [60.0, 40.0],
        }
    )
    conjuntos = pd.DataFrame(
        {
            "id_ons_conjunto": ["CJU_E", "CJU_E"],
            "ceg": ["A1", "A2"],
            "dat_fimrelacionamento": ["2024-10-29", "2023-02-01"],
        }
    )
    usinas = pd.DataFrame(
        {"id_ons": ["CJU_E"], "nom_usina": ["Conj E"], "uf": ["BA"], "fonte": ["EOL"], "ceg": ["-"]}
    )
    mapa = pac.construir_mapa(usinas, modalidade, conjuntos)
    assert len(mapa) == 1 and mapa["pac_nome"].iloc[0] == "X"  # so a composicao de 2024-10-29
    assert mapa["vigencia"].iloc[0] == "encerrado em 2024-10-29"
    assert not mapa.duplicated(["id_ons", "pac_nome"]).any()


def test_rateio_por_potencia():
    modalidade = pd.DataFrame(
        {
            "ceg": ["A1", "A2"],
            "nom_pontoconexao": ["SE X 500 kV", "SE Y 230 kV"],
            "val_potenciaautorizada": [60.0, 40.0],
        }
    )
    conjuntos = pd.DataFrame(
        {
            "id_ons_conjunto": ["CJU_A", "CJU_A"],
            "ceg": ["A1", "A2"],
            "dat_fimrelacionamento": [None, None],
        }
    )
    usinas = pd.DataFrame(
        {"id_ons": ["CJU_A"], "nom_usina": ["Conj A"], "uf": ["BA"], "fonte": ["EOL"], "ceg": ["-"]}
    )
    mapa = pac.construir_mapa(usinas, modalidade, conjuntos)
    assert len(mapa) == 2 and set(mapa["metodo"]) == {"rateio_potencia"}
    assert set(mapa["confianca"]) == {"media"}
    assert mapa["fracao_potencia"].sum() == pytest.approx(1.0)
    assert mapa.set_index("pac_nome").loc["X", "fracao_potencia"] == pytest.approx(0.6)
    lista = pac.pacs_distintos(mapa, pd.Series({"CJU_A": 1000.0}))
    assert lista.set_index("pac_nome").loc["Y", "eng_gwh"] == pytest.approx(0.4)


def test_normalizar_seccionamentos():
    n = pac.normalizar_pac
    assert n("SECCIONAMENTO LT 500 KV AÇU III - JOÃO CÂMARA")[0] == "SECC. LT ACU 3 – JOAO CAMARA 3"
    assert n("LT 500 KV AÇÚ III – JOÃO CÂMARA III")[0] == "SECC. LT ACU 3 – JOAO CAMARA 3"
    assert (
        n("SECC LT 500 KV MONTE VERDE – JOÃO CÂMARA III")[0]
        == n("SECC. LT 500 KV JOÃO CÂMARA III – MONTE VERDE")[0]
    )
    juazeiro = {
        n(t)[0]
        for t in (
            "SECC. LT 500 KV U. SOBRADINHO - JUAZEIRO III",
            "SECC LT SOBRADINHO/JUAZEIRO DA BAHIA III C1",
            "SECCIONAMENTO C1 DA LT 500 KV SOBRADINHO –JUA",
            "SECCIONAMENTO LT 500 KV U.SOBRADINHO / JUAZEI",
        )
    }
    assert juazeiro == {"SECC. LT JUAZEIRO 3 – SOBRADINHO"}
    assert n("SEC LT 500 KV BOM JESUS DA LAPA II – GENTIO D")[0] == (
        "SECC. LT BOM JESUS DA LAPA 2 – GENTIO DO OURO 2"
    )
    assert n("SE CURRARIS NOVOS II 230 KV")[0] == "CURRAIS NOVOS 2"
    assert n("SE 69 kV Igaporã II - ICG")[0] == "IGAPORA 2 ICG"  # ICG fica separado
    assert n("SE Queimada Nova 500 kV")[0] != n("SE QUEIMADA NOVA II 500 KV")[0]
