"""Parser de dsc_restricao com exemplos reais do dataset (2025-09 em diante)."""

from __future__ import annotations

from coff import descricoes as d

EXEMPLOS = {
    "freq": "Controle de frequência do SIN.",
    "fnese": "Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste - Conforme SGI 67.632-25",
    "acu": (
        "Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NA LT 500 KV AÇU III / JAGUARUANA II "
        "– C1(V7) - IO-ON.NE.5NE"
    ),
    "rns": (
        "Controle de inequação: CONTROLE DE CARREGAMENTO DA TRANSFORMAÇÃO 500/345 KV DA SE RIO "
        "NOVO DO SUL COM GVA6/MTUM/RNS RADIALIZADA - IO-ON.SE.5RJ"
    ),
    "fjusc": (
        "Controle de inequação: LIMITE DE FJUSC EM FUNÇÃO DA POTÊNCIA TRANSMITIDA PELOS BIPOLOS "
        "XINGU / ESTREITO E XINGU / TERMINAL RIO - IO-ON.SENE revisão 84"
    ),
    "deslig": "Desligamento das LT 525 kV Povo Novo / Marmeleiro C2. SGI N° 46.066-26",
}


def test_normalizacao_remove_referencias_numericas():
    a = d.normalizar(EXEMPLOS["fnese"])
    b = d.normalizar("Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste - Conforme SGI 43.225-26")
    assert a == b == "Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste"
    assert d.normalizar(EXEMPLOS["fjusc"]).endswith("TERMINAL RIO - IO-ON.SENE")
    assert (
        d.normalizar(EXEMPLOS["deslig"]) == "Desligamento das LT 525 kV Povo Novo / Marmeleiro C2"
    )
    assert d.normalizar("  Controle  de\ninequação: X  ") == "Controle de inequação: X"
    assert (
        d.normalizar(
            "Controle de inequação: Perda da LT 345 kV Campos / Rio Novo do Sul C1 (2.2) "
            "- SGI 61.162-25"
        )
        == "Controle de inequação: Perda da LT 345 kV Campos / Rio Novo do Sul C1"
    )
    assert d.normalizar(None) == "" and d.normalizar(float("nan")) == ""


def test_tipo_elemento_tensao_classe():
    r = d.analisar(EXEMPLOS["freq"])
    assert (r.tipo, r.elemento, r.classe) == ("Controle de frequência", "SIN", "frequencia")
    r = d.analisar(EXEMPLOS["fnese"])
    assert (r.tipo, r.elemento, r.classe) == ("Controle do fluxo", "FNESE", "exportacao")
    r = d.analisar(EXEMPLOS["acu"])
    assert r.tipo == "Limitação da transmissão" and r.tensao_kv == 500 and r.classe == "local"
    assert r.elemento == "LT 500 kV Açu III / Jaguaruana II"
    r = d.analisar(EXEMPLOS["rns"])
    assert r.tipo == "Controle de inequação" and r.tensao_kv == 500 and r.classe == "local"
    assert r.elemento.startswith("Transformação 500/345 kV da SE Rio Novo do Sul")
    r = d.analisar(EXEMPLOS["fjusc"])
    assert r.tipo == "Controle de inequação" and r.elemento.startswith("Bipolos Xingu")
    assert r.classe == "local"
    r = d.analisar(EXEMPLOS["deslig"])
    assert (
        r.tipo == "outro"
        and r.elemento == "LT 525 kV Povo Novo / Marmeleiro C2"
        and r.tensao_kv == 525
    )
    r = d.analisar("Controle do fluxo: FNS_FNESE # Somatório de FNS+FNESE - Conforme SGI 22.502-26")
    assert r.elemento == "FNS+FNESE" and r.classe == "exportacao"


def test_classe_efetiva():
    assert d.classe_efetiva("exportacao", "sistemica") == "intercâmbio nomeado"
    assert d.classe_efetiva("local", "sistemica") == "corredor de exportação"
    assert d.classe_efetiva("local", "local") == "local NE"
    assert d.classe_efetiva("outro", "local") == "outro"
    assert d.classe_efetiva("frequencia", "sistemica") == "outro"
