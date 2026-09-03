"""Extracao da NT 02: regex das tabelas, regra de resultado, elementos e validacao do INAB."""

from __future__ import annotations

import pandas as pd

from coff import nt02

TRECHO_4 = (
    "Tabela 4-2 apresenta os quantitativos UF BARRAMENTO CANDIDATO TENSÃO (kV) MUST CADASTRADO "
    "2027 2028 2029 2030 2031 BA Sol do Sertão (SDS) 500 0 0 586,9 586,9 586,9 "
    "RN Touros (TRS) 230 2,5 2,5 2,5 2,5 2,5 4.3 A apresenta UF BARRAMENTO CANDIDATO "
    "TENSÃO (kV) MUST CADASTRADO 2027 2028 2029 2030 2031 PR Segredo (SGD) 525 0 0 0 1.266 1.266 "
    "pt-BR5 "
)
TRECHO_6 = (
    "pt-BR6  A seguir Tabela 6-52: Segmento Geração  Capacidade Remanescente e Fatores Limitantes "
    "da Bahia e Sergipe  Produto 2031 CAPACIDADE BARRAMENTO SUBÁREA ÁREA BARRAMENTO SUBÁREA ÁREA "
    "SE Sol do Sertão (SDS) 500 0 0 0 Incapacidade de acréscimo de nova geração devido a violação "
    "dos limites de intercâmbio ou de fluxo previamente definidos. SE Touros (TRS) 230 0 0 0 "
    "Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de "
    "fluxo previamente definidos. Tabela 6-11: Segmento Geração para Usinas do LRCAP 2026 "
    "Capacidade Remanescente e Fatores Limitantes do Paraná  Produto 2031 CAPACIDADE BARRAMENTO "
    "SUBÁREA ÁREA BARRAMENTO SUBÁREA ÁREA Segredo (SGD) 525 1.266 1.266 1.266 Não foram "
    "encontradas violações na região em análise para o valor cadastrado. "
)


def test_tabelas_4_2_e_4_3():
    tab = nt02.tabelas_4_2_e_4_3(TRECHO_4)
    assert list(tab["sigla"]) == ["SDS", "TRS", "SGD"]
    assert list(tab["lrcap"]) == [False, False, True]
    assert tab.loc[0, "must_2031"] == 586.9 and tab.loc[2, "must_2031"] == 1266.0
    assert tab.loc[1, "must_2027"] == 2.5 and tab.loc[0, "uf"] == "BA"


def test_tabelas_secao_6():
    s6 = nt02.tabelas_secao_6(TRECHO_6)
    assert list(s6["sigla"]) == ["SDS", "TRS", "SGD"]
    assert s6.loc[0, "cap_rem_barramento"] == 0.0 and s6.loc[2, "cap_rem_barramento"] == 1266.0
    assert s6.loc[0, "fator_limitante"].startswith("Incapacidade de acréscimo")
    assert s6.loc[2, "fator_limitante"].startswith("Não foram encontradas")
    assert bool(s6.loc[2, "lrcap"]) and s6.loc[2, "regiao"] == "Paraná"


def test_resultado_e_elementos():
    assert nt02.resultado_de(586.9, 0.0, "Incapacidade ...", False) == "INAB"
    assert nt02.resultado_de(300.0, 300.0, "Não foram ... Configuração G descrita", False) == "ADVC"
    assert nt02.resultado_de(807.5, 360.0, "Sobrecarga na LT", False) == "PC"
    assert nt02.resultado_de(17.2, 17.2, "Não foram encontradas violações", False) == "AD"
    assert nt02.elementos_do_fator(
        "Incapacidade ... limites de intercâmbio ou de fluxo ..."
    ).startswith("limites de intercâmbio/fluxo")
    el = nt02.elementos_do_fator(
        "Sobrecarga na LT 230 kV C. Dourada - Itumbiara em regime normal de operação."
    )
    assert el == "LT 230 kV C. Dourada - Itumbiara"
    el2 = nt02.elementos_do_fator(
        "Sobrecarga na LT 230 kV Alegrete 2 Maçambará, na contingência da LT 230 kV Maçambará UTE "
        "Uruguaiana, na carga máxima noturna de inverno."
    )
    assert el2 == "LT 230 kV Alegrete 2 Maçambará; LT 230 kV Maçambará UTE Uruguaiana"


def test_validacao_inab_por_uf():
    texto = TRECHO_4 + TRECHO_6
    info = pd.DataFrame({"uf": ["BA", "RN", "PR"], "inab_mw": [586.9, 10.0, None]})
    res = nt02.consolidar(texto, info)
    val = res.validacao.set_index("uf")
    assert val.loc["BA", "inab_nt_mw"] == 586.9 and val.loc["BA", "dif_mw"] == 0.0
    assert val.loc["RN", "inab_nt_mw"] == 2.5 and res.divergencias == [
        "RN: NT 2.5 MW vs infográfico 10.0 MW (dif -7.5)"
    ]
    assert list(res.barramentos["resultado"]) == ["INAB", "INAB", "AD"]
