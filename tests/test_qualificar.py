"""Testes das regras R1–R11 sobre a fixture sintetica (valores calculados a mao)."""

from __future__ import annotations

import pandas as pd
import pytest

from coff import carregar, qualificar

# ordem da fixture: 0 sem restricao; 1 ENE (duplicado por 6); 2 REL final<ref; 3 ENE ger>=ref;
# 4 CNF limite=0; 5 codigo XYZ; 6 duplicata mantida (ultima); 7 geracao negativa.


@pytest.fixture
def q(df_usina_8_instantes):
    return qualificar.qualificar(carregar.tipar(df_usina_8_instantes), "coalesce", 0.5)


def test_nenhuma_linha_descartada(q):
    assert len(q) == 8


def test_r1_restrito_e_sem_restricao(q):
    assert q["restrito"].tolist() == [False, True, True, True, True, True, True, True]
    assert q.loc[0, "motivo"] == "sem_restricao" and not q.loc[0, "qualificado"]


def test_r2_codigo_desconhecido(q):
    assert q.loc[5, "motivo"] == "codigo_desconhecido" and q.loc[5, "eng_mwh"] == 0
    assert pd.isna(q.loc[5, "categoria"])
    assert q.loc[1, "categoria"] == "energetica" and q.loc[2, "categoria"] == "eletrica"


def test_r3_origem(q):
    assert q.loc[1, "origem"] == "sistemica" and q.loc[2, "origem"] == "local"
    assert not q["origem_desconhecida"].any()


def test_r4_duplicata_mantem_a_ultima(q):
    assert q.loc[1, "motivo"] == "duplicata" and not q.loc[1, "qualificado"]
    assert q.loc[6, "qualificado"] and q.loc[6, "eng_mw"] == 20.0  # 31 - 11


def test_r4_instante_invalido(df_usina_8_instantes):
    df = df_usina_8_instantes.copy()
    df.loc[3, "din_instante"] = "nao e data"
    q = qualificar.qualificar(carregar.tipar(df))
    assert q.loc[3, "motivo"] == "instante_invalido" and q.loc[3, "eng_mwh"] == 0


def test_r5_valor_nulo(df_usina_8_instantes):
    df = df_usina_8_instantes.copy()
    df.loc[4, "val_geracao"] = None
    q = qualificar.qualificar(carregar.tipar(df))
    assert q.loc[4, "motivo"] == "valor_nulo"


def test_r6_referencia_efetiva(q, df_usina_8_instantes):
    assert q.loc[2, "ref_ef"] == 20.0 and q.loc[2, "eng_mwh"] == 5.0  # (20-10)*0.5
    q_ref = qualificar.qualificar(carregar.tipar(df_usina_8_instantes), "referencia", 0.5)
    assert q_ref.loc[2, "ref_ef"] == 30.0 and q_ref.loc[2, "eng_mwh"] == 10.0
    with pytest.raises(ValueError):
        qualificar.qualificar(carregar.tipar(df_usina_8_instantes), "final")


def test_r7_geracao_negativa(q):
    assert q.loc[7, "geracao_negativa"] and q.loc[7, "ger_calc"] == 0.0
    assert q.loc[7, "eng_mwh"] == 4.0  # (8 - 0) * 0.5
    assert q.loc[7, "energia_gerada_mwh"] == 0.0


def test_r8_eng_e_restrito_sem_eng(q):
    assert q.loc[3, "qualificado"] and q.loc[3, "eng_mwh"] == 0 and q.loc[3, "restrito_sem_eng"]
    assert q["restrito_sem_eng"].sum() == 1
    assert q["eng_mwh"].sum() == pytest.approx(10 + 5 + 0 + 20 + 4)  # linhas 6,2,3,4,7


def test_r9_limite_flags(q):
    assert q.loc[4, "limite_zero"] and q.loc[4, "qualificado"] and q.loc[4, "eng_mwh"] == 20.0
    assert q.loc[3, "limite_nao_vinculante"]  # limite 30 > ref 25
    assert q["limite_nao_vinculante"].sum() == 1


def test_r10_disponibilidade(df_usina_8_instantes):
    df = df_usina_8_instantes.copy()
    df.loc[6, "val_disponibilidade"] = 0.0
    q = qualificar.qualificar(carregar.tipar(df))
    assert q.loc[6, "disponibilidade_zero"] and q.loc[6, "qualificado"]  # so flag por padrao
    assert q.loc[6, "ref_maior_que_disp"] and q.loc[6, "ger_maior_que_disp"]
    q2 = qualificar.qualificar(carregar.tipar(df), excluir_disp_zero=True)
    assert q2.loc[6, "motivo"] == "disponibilidade_zero" and q2.loc[6, "eng_mwh"] == 0


def test_energia_gerada_todas_as_linhas(q):
    # 10,10,10,30,0,5,11,-2->0 = 76 MW x 0.5 h
    assert q["energia_gerada_mwh"].sum() == pytest.approx(38.0)


def test_r11_lacunas(q):
    lac = qualificar.lacunas_por_usina_mes(q, 0.5)
    assert len(lac) == 1
    assert lac.loc[0, "presentes"] == 8 and lac.loc[0, "esperados"] == 31 * 48


def test_relatorio(q):
    rel = qualificar.relatorio_qualificacao(q, "coalesce", 0.5)
    texto = qualificar.relatorio_markdown(rel)
    assert rel.total == 8
    assert rel.codigos_desconhecidos.to_dict() == {"XYZ": 1}
    assert rel.eng_total_mwh["EOL"] == pytest.approx(39.0)
    assert "codigo_desconhecido" in texto and "limite_zero" in texto
