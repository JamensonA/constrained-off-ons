"""Testes das agregacoes sobre o mes sintetico de 2 usinas (valores a mao).

USI_A (UFV, 2025-02): h0 ENE ger 10 ref 20 -> 5 MWh; h1 sem restricao; h2 CNF ger 0 ref 30
-> 15 MWh; h3 REL ger 5 ref 25 final 20 -> 7,5 MWh (coalesce) / 10 MWh (referencia).
Energia gerada A = (10+10+0+5) x 0,5 = 12,5 MWh. USI_B (CE): sem restricao, 2 MW x 4 -> 4 MWh.
"""

from __future__ import annotations

import pytest

from coff import carregar, metricas, qualificar


@pytest.fixture
def q(df_mes_2_usinas):
    return qualificar.qualificar(carregar.tipar(df_mes_2_usinas), "coalesce", 0.5)


def test_eng_por_mes(q):
    tab = metricas.eng_por_mes(q)
    assert list(tab.columns) == ["EOL", "UFV"]
    assert tab.loc["2025-02", "UFV"] == pytest.approx(27.5)
    assert tab.loc["2025-02", "EOL"] == 0.0


def test_eng_por_categoria(q):
    tab = metricas.eng_por_categoria(q).set_index("categoria")["eng_mwh"]
    assert tab["energetica"] == 5.0 and tab["confiabilidade"] == 15.0
    assert tab["eletrica"] == pytest.approx(7.5)


def test_eng_por_subsistema(q):
    tab = metricas.eng_por_subsistema(q)
    linha = tab.iloc[0]
    assert (linha["subsistema"], linha["estado"]) == ("NE", "BA")
    assert linha["eng_mwh"] == pytest.approx(27.5)
    assert linha["energia_gerada_mwh"] == pytest.approx(12.5)
    assert linha["taxa_corte"] == pytest.approx(27.5 / 40)
    ce = tab[tab["estado"] == "CE"].iloc[0]
    assert ce["eng_mwh"] == 0.0 and ce["energia_gerada_mwh"] == pytest.approx(4.0)


def test_top_usinas_e_taxa_de_corte(q):
    tab = metricas.top_usinas(q, n=15)
    assert list(tab["id_ons"]) == ["USI_A", "USI_B"]
    a = tab.iloc[0]
    assert a["eng_mwh"] == pytest.approx(27.5) and a["energia_gerada_mwh"] == pytest.approx(12.5)
    assert a["taxa_corte"] == pytest.approx(27.5 / 40)
    assert tab.iloc[1]["taxa_corte"] == 0.0
    assert len(metricas.top_usinas(q, n=1)) == 1


def test_perfil_hora_mes(q):
    perfil = metricas.perfil_hora_mes(q)
    assert perfil.shape == (24, 1)
    assert perfil.loc[0, "2025-02"] == pytest.approx(5 / 28)
    assert perfil.loc[2, "2025-02"] == pytest.approx(15 / 28)
    assert perfil.loc[5, "2025-02"] == 0.0


def test_top_descricoes(q):
    tab = metricas.top_descricoes(q, n=20)
    assert list(tab["dsc_restricao"]) == ["CNF", "REL", "ENE"]
    assert tab.iloc[0]["eng_mwh"] == 15.0 and tab.iloc[0]["registros"] == 1


def test_sensibilidade_referencia(q):
    tab = metricas.sensibilidade_referencia(q, 0.5).set_index("categoria")
    assert tab.loc["eletrica", "eng_coalesce_mwh"] == pytest.approx(7.5)
    assert tab.loc["eletrica", "eng_referencia_mwh"] == pytest.approx(10.0)
    assert tab.loc["eletrica", "dif_abs_mwh"] == pytest.approx(-2.5)
    assert tab.loc["eletrica", "dif_rel"] == pytest.approx(-0.25)
    assert tab.loc["energetica", "dif_abs_mwh"] == 0.0


def test_ocorrencias_par_vazio(q):
    assert metricas.ocorrencias_par(q).empty


def test_resumo_anual(q):
    tab = metricas.resumo_anual(q)
    assert len(tab) == 1
    linha = tab.iloc[0]
    assert (linha["ano"], linha["fonte"]) == (2025, "UFV")
    assert linha["eng_gwh"] == pytest.approx(0.0275, abs=1e-4)
    assert linha["taxa_corte_pct"] == pytest.approx(62.5)


def test_taxa_mensal(q):
    tab = metricas.taxa_mensal(q)
    assert list(tab["mes"]) == ["2025-02"]
    assert tab.loc[0, "eng_mwh"] == pytest.approx(27.5)
    assert tab.loc[0, "taxa_corte"] == pytest.approx(27.5 / 44)
    assert tab.loc[0, "taxa_corte_UFV"] == pytest.approx(27.5 / 44)


def test_eng_por_uf_e_cruzamento(q):
    import pandas as pd

    tab = metricas.eng_por_uf(q, "2025-01").set_index("uf")
    assert list(tab.index) == ["BA", "CE"]
    assert tab.loc["BA", "eng_gwh"] == pytest.approx(0.0275)
    assert tab.loc["BA", "eng_energetica_gwh"] == pytest.approx(0.005)
    assert tab.loc["BA", "eng_confiabilidade_gwh"] == pytest.approx(0.015)
    assert tab.loc["BA", "eng_eletrica_gwh"] == pytest.approx(0.0075)
    assert tab.loc["BA", "taxa_corte"] == pytest.approx(27.5 / 40)
    assert tab.loc["CE", "eng_gwh"] == 0.0 and tab.loc["CE", "energia_gerada_gwh"] == pytest.approx(
        0.004
    )
    assert metricas.eng_por_uf(q, "2025-03").empty

    temporada = pd.DataFrame(
        {
            "uf": ["BA", "PI"],
            "ad_mw": [100.0, None],
            "advc_mw": [None, None],
            "pc_mw": [None, None],
            "inab_mw": [300.0, 50.0],
        }
    )
    cruz = metricas.cruzar_temporada(tab.reset_index(), temporada).set_index("uf")
    assert set(cruz.index) == {"BA", "CE", "PI"}
    assert cruz.loc["BA", "cadastrado_mw"] == 400.0 and cruz.loc[
        "BA", "frac_inab"
    ] == pytest.approx(0.75)
    assert cruz.loc["PI", "frac_inab"] == pytest.approx(1.0) and cruz.loc["PI", "eng_gwh"] == 0.0
    assert pd.isna(cruz.loc["CE", "frac_inab"])
    rho, n = metricas.spearman_taxa_inabilitacao(cruz.reset_index())
    assert n == 1 and rho != rho  # so BA tem os dois dados -> NaN


def test_spearman_sem_scipy():
    import pandas as pd

    cruz = pd.DataFrame(
        {
            "uf": list("ABCD"),
            "taxa_corte": [0.1, 0.2, 0.3, 0.4],
            "frac_inab": [0.0, 0.5, 0.6, 1.0],
            "eng_gwh": [1, 1, 1, 1],
            "energia_gerada_gwh": [1, 1, 1, 1],
        }
    )
    rho, n = metricas.spearman_taxa_inabilitacao(cruz)
    assert n == 4 and rho == pytest.approx(1.0)
    cruz["frac_inab"] = [1.0, 0.6, 0.5, 0.0]
    assert metricas.spearman_taxa_inabilitacao(cruz)[0] == pytest.approx(-1.0)


def test_taxas_por_razao_somam_a_taxa_total(q):
    import pandas as pd

    tab = metricas.taxas_por_razao_uf(metricas.eng_por_uf(q, "2025-01"))
    assert list(tab["uf"]) == ["BA"]  # CE tem ENG = 0 e sai
    linha = tab.iloc[0]
    assert linha["taxa_ene"] + linha["taxa_rede"] == pytest.approx(linha["taxa_total"])
    assert linha["taxa_cnf"] + linha["taxa_rel"] == pytest.approx(linha["taxa_rede"])
    assert linha["taxa_total"] == pytest.approx(27.5 / 40)
    assert linha["taxa_ene"] == pytest.approx(5 / 40)
    assert linha["share_rede"] == pytest.approx(22.5 / 27.5)
    temporada = pd.DataFrame(
        {"uf": ["BA"], "ad_mw": [100.0], "advc_mw": [None], "pc_mw": [None], "inab_mw": [300.0]}
    )
    cruz = metricas.cruzar_por_razao(tab, temporada)
    assert cruz.loc[0, "frac_inab"] == pytest.approx(0.75)


def test_spearman_permutacao_extremos():
    x = [1, 2, 3, 4, 5, 6, 7, 8]
    rho, p, n, metodo = metricas.spearman_permutacao(x, x)  # monotonico perfeito
    assert rho == pytest.approx(1.0) and n == 8 and metodo.startswith("exato")
    assert p == pytest.approx(2 / 40320)  # so a identidade e a inversa atingem |rho| = 1
    rho0, p0, _, _ = metricas.spearman_permutacao([1, 2, 3, 4], [2, 4, 1, 3])  # rho = 0
    assert rho0 == pytest.approx(0.0) and p0 == 1.0
    rho9, p9, n9, metodo9 = metricas.spearman_permutacao(list(range(9)), list(range(9)), 2000)
    assert n9 == 9 and "2000" in metodo9 and rho9 == pytest.approx(1.0) and p9 < 0.01
    _, pn, _, m = metricas.spearman_permutacao([1, 2], [1, 2])
    assert m == "insuficiente" and pn != pn
