"""Testes de schema, tipagem, delta t e leitura estrita de CSV."""

from __future__ import annotations

import pandas as pd
import pytest

from coff import carregar
from coff.categorias import categoria_de, normalizar_codigo, origem_de


def test_validar_schema_aceita_16_colunas(df_usina_8_instantes):
    assert carregar.validar_schema(df_usina_8_instantes.columns[:16], "teste") is None


def test_validar_schema_tolera_ausencia_de_dsc_restricao(df_usina_8_instantes):
    cols = [c for c in df_usina_8_instantes.columns[:16] if c != "dsc_restricao"]
    aviso = carregar.validar_schema(cols, "EOL 2023_01.csv")
    assert aviso is not None and "dsc_restricao" in aviso and "tolerado" in aviso


def test_ler_arquivo_cria_dsc_restricao_nula_em_mes_antigo(tmp_path, df_usina_8_instantes):
    caminho = tmp_path / "RESTRICAO_COFF_EOLICA_2023_01.csv"
    df_usina_8_instantes.iloc[:, :15].to_csv(caminho, sep=";", index=False)
    df, malformadas, divergencia = carregar.ler_arquivo(caminho, "EOL")
    assert malformadas == 0 and divergencia is not None
    assert df["dsc_restricao"].isna().all() and list(df.columns[:16]) == list(
        carregar.COLUNAS_ESPERADAS
    )


def test_validar_schema_reclama_de_coluna_faltante_e_extra(df_usina_8_instantes):
    cols = list(df_usina_8_instantes.columns[:16])
    cols.remove("dsc_restricao")
    cols.append("coluna_nova")
    with pytest.raises(carregar.SchemaInvalidoError, match="faltam=\\['dsc_restricao'\\]"):
        carregar.validar_schema(cols, "arquivo_x")


def test_tipar_converte_sem_descartar(df_usina_8_instantes):
    df = df_usina_8_instantes.copy()
    df.loc[0, "din_instante"] = "data invalida"
    tipado = carregar.tipar(df)
    assert len(tipado) == 8
    assert tipado["din_instante"].isna().sum() == 1
    assert tipado.loc[0, "din_instante_bruto"] == "data invalida"
    assert tipado["val_geracao"].dtype == "float64"
    assert tipado["val_geracaoreferenciafinal"].isna().sum() == 7
    assert str(tipado["id_ons"].dtype) == "category"


def test_inferir_delta_t_30_min(df_usina_8_instantes):
    df = carregar.tipar(df_usina_8_instantes)
    dt, dist = carregar.inferir_delta_t(df)
    assert dt == pd.Timedelta(minutes=30)
    carregar.verificar_delta_t(dt, "EOL")
    assert dist.iloc[0] >= 5


def test_delta_t_horario_aborta(df_usina_8_instantes):
    df = carregar.tipar(df_usina_8_instantes.drop_duplicates("din_instante"))
    df["din_instante"] = df["din_instante"].iloc[0] + pd.to_timedelta(range(len(df)), unit="h")
    dt, _ = carregar.inferir_delta_t(df)
    with pytest.raises(carregar.DeltaTInesperadoError):
        carregar.verificar_delta_t(dt, "EOL")


def test_ler_csv_conta_linhas_malformadas(tmp_path, df_usina_8_instantes):
    caminho = tmp_path / "RESTRICAO_COFF_EOLICA_2025_01.csv"
    df_usina_8_instantes.iloc[:, :16].to_csv(caminho, sep=";", index=False)
    with caminho.open("a", encoding="utf-8") as f:
        f.write("NE;NORDESTE;BA;campo;a;mais\n")  # linha com numero errado de campos
    df, malformadas, divergencia = carregar.ler_arquivo(caminho, "EOL")
    assert malformadas == 1 and divergencia is None
    assert len(df) == 8
    assert df["periodo"].iloc[0] == "2025_01"
    assert df["fonte"].iloc[0] == "EOL"


def test_contar_codigos_por_mes(df_usina_8_instantes):
    tab = carregar.contar_codigos_por_mes(carregar.tipar(df_usina_8_instantes))
    linha = tab.iloc[0]
    assert linha["ENE"] == 4 and linha["REL"] == 1 and linha["CNF"] == 1 and linha["XYZ"] == 1
    assert linha["(nulo)"] == 1
    assert "PAR" not in tab.columns


def test_categorias():
    assert categoria_de(" ene ") == "energetica"
    assert categoria_de("REL") == "eletrica"
    assert categoria_de("CNF") == "confiabilidade"
    assert categoria_de("PAR") == "parecer de acesso"
    assert categoria_de("XYZ") is None
    assert categoria_de(None) is None
    assert normalizar_codigo(float("nan")) is None
    assert origem_de("loc") == "local" and origem_de("SIS") == "sistemica"
