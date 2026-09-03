"""Mapa usina/conjunto -> ponto de conexao (PAC) a partir do cadastro aberto do ONS.

Etapa 3 do cruzamento por ponto de conexao. Fontes (CKAN): ``modalidade-usina``
(``nom_pontoconexao`` por usina, chave ``ceg``) e ``usina_conjunto`` (relacao
conjunto -> usinas). O nome do ponto de conexao e texto livre e e normalizado por
regras; conjuntos com mais de um PAC real recebem rateio pela potencia autorizada.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

URLS = {
    "modalidade_usina": (
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/modalidade_usina/MODALIDADE_USINA.csv"
    ),
    "usina_conjunto": (
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/usina_conjunto/"
        "RELACIONAMENTO_USINA_CONJUNTO.csv"
    ),
}
LIMIAR_PAC_UNICO = 0.90

_TENSAO = re.compile(r"(\d{2,3})(?:[,.]\d+)?\s*K\s*V", re.I)
_ROMANOS = {"II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8"}
_PREFIXOS = re.compile(r"^(?:SE|SUB|SUBESTACAO|SUBESTAÇÃO|S\.E\.|BARRA|BARRAMENTO)\s+", re.I)
_SECC = re.compile(r"\b(?:SECCIONAMENTO|SECC\.?|SECIONAMENTO|SEC\.?)\b", re.I)
_ALIASES = {
    "CURRARIS NOVOS": "CURRAIS NOVOS",
    "JUAZEIRO DA BAHIA": "JUAZEIRO",
    "ACU": "ACU",
}
_PREPOSICOES = {"DE", "DA", "DO", "DAS", "DOS", "EM", "NA", "NO", "E"}


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def normalizar_pac(texto: object) -> tuple[str | None, float | None]:
    """Chave normalizada do ponto de conexao e tensao (kV).

    Ex.: "SE ACU III 500,0 kV" -> ("ACU 3", 500.0); "SE Açu III 500 kV" -> ("ACU 3", 500.0);
    "Rede de Distribuição 13,8 kV" -> ("REDE DE DISTRIBUICAO", 13.8).
    """
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None, None
    t = _sem_acento(str(texto)).upper().strip()
    if not t:
        return None, None
    m = _TENSAO.search(t)
    tensao = None
    if m:
        bruto = m.group(0)
        num = re.match(r"(\d{2,3})(?:[,.](\d+))?", bruto)
        tensao = float(num.group(1) + ("." + num.group(2) if num.group(2) else ""))
        t = t.replace(bruto, " ")
    t = _SECC.sub("SECC", t)
    t = re.sub(r"\bU\.\s*", "", t)  # "U. SOBRADINHO" -> "SOBRADINHO"
    t = re.sub(r"\((?:ANTIGA|EX)[^)]*\)", " ", t)
    t = re.sub(r"[^\w\s]", " ", t)
    t = _PREFIXOS.sub("", t.strip())
    t = re.sub(r"\bC\d\b", " ", t)  # circuito
    t = re.sub(r"\bDUPL[OA]\b", " ", t)
    for de, para in _ALIASES.items():
        t = re.sub(rf"\b{de}\b", para, t)
    tokens = [_ROMANOS.get(tok, tok) for tok in t.split()]
    chave = " ".join(tokens).strip()
    secc = _chave_seccionamento(chave)
    if secc:
        return secc, tensao
    return (chave or None), tensao


def _chave_seccionamento(chave: str) -> str | None:
    """Seccionamento de LT/LD -> "SECC. LT <A> – <B>" com o par em ordem alfabetica.

    Aceita "SECC LT A B", "SECC DA LT A B", "LT A B" (LT como ponto de conexao) e
    variantes com LD; preposicoes, circuito e "duplo" ja foram removidos. Devolve None
    se nao for um seccionamento ou se o par nao puder ser separado.
    """
    tokens = chave.split()
    if not tokens:
        return None
    e_secc = tokens[0] == "SECC"
    if e_secc:
        tokens = tokens[1:]
    while tokens and tokens[0] in _PREPOSICOES:
        tokens = tokens[1:]
    if not tokens or tokens[0] not in ("LT", "LD"):
        return None
    tipo = tokens[0]
    tokens = tokens[1:]
    while tokens and tokens[0] in _PREPOSICOES:
        tokens = tokens[1:]
    resto = " ".join(tokens)
    # o par vem separado por hifen/travessao/barra (ja virou espaco) -> usa o marcador
    # original quando existir; caso contrario tenta a divisao pelo ultimo numeral
    partes = _dividir_par(resto)
    if partes is None:
        return None
    a, b = sorted(_resolver_truncado(x.strip()) for x in partes)
    if {a, b} == {"ACU 3", "JOAO CAMARA"}:  # decisao do autor: LT Acu 3 – Joao Camara = ... 3
        a, b = "ACU 3", "JOAO CAMARA 3"
    return f"SECC. {tipo} {a} – {b}"


def _resolver_truncado(nome: str) -> str:
    """Completa nomes truncados pelo cadastro ("JUA", "GENTIO D") com a SE conhecida.

    Resolve quando o nome tem >= 3 letras e todos os candidatos conhecidos que comecam
    com ele sao prefixos uns dos outros (escolhe o mais longo).
    """
    if nome in _SES_CONHECIDAS or len(nome) < 3:
        return nome
    candidatos = sorted((k for k in _SES_CONHECIDAS if k.startswith(nome)), key=len)
    if not candidatos:
        return nome
    maior = candidatos[-1]
    if all(maior.startswith(c) for c in candidatos):
        return maior
    return nome


def _dividir_par(texto: str) -> tuple[str, str] | None:
    """Divide "ACU 3 JOAO CAMARA 3" em ("ACU 3", "JOAO CAMARA 3") usando os numerais."""
    toks = texto.split()
    if len(toks) < 2:
        return None
    # candidatos: cortar apos um token numerico (ex.: "ACU 3 | JOAO CAMARA 3")
    for i in range(1, len(toks)):
        if re.fullmatch(r"\d+", toks[i - 1]) and i < len(toks):
            return " ".join(toks[:i]), " ".join(toks[i:])
    # sem numeral: usa a lista de SEs conhecidas de duas palavras mais comuns
    for i in range(1, len(toks)):
        a, b = " ".join(toks[:i]), " ".join(toks[i:])
        if a in _SES_CONHECIDAS or b in _SES_CONHECIDAS:
            return a, b
    return None


# SEs conhecidas (nomes normalizados) usadas para separar pares e completar truncamentos
_SES_CONHECIDAS = {
    "SOBRADINHO",
    "JUAZEIRO 3",
    "MONTE VERDE",
    "JOAO CAMARA 3",
    "ACU 3",
    "BOM JESUS DA LAPA 2",
    "GENTIO DO OURO 2",
    "AGUA VERMELHA",
    "JALES",
    "VOTUPORANGA 2",
    "VOTUPORANGA 1",
    "IBIAPINA 2",
    "PIRIPIRI",
    "BANABUIU",
    "MOSSORO 2",
    "MILAGRES",
    "BOM NOME",
    "MANGA 3",
    "JANAUBA 1",
    "JANAUBA 2",
    "JANAUBA 3",
    "JUPIA",
    "TRES IRMAOS",
    "IGAPORA 3",
    "PAULO AFONSO 4",
    "OLINDINA",
    "LAGOA NOVA 2",
    "CAMPINA GRANDE 3",
    "EXTREMOZ",
    "SALGUEIRO",
    "SERRITA",
    "SAO ROMAO",
    "URUCUIA 1",
    "ARAXA 2",
    "JAGUARA",
    "BURITIZEIRO 1",
    "UHE TRES MARIAS",
    "JOAO PINHEIRO 3",
    "VARZEA DA PALMA 1",
    "MONTES CLAROS 2",
    "IRAPE",
    "PIRAPORA 2",
}


def carregar_registros(pasta_externo: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Le (baixando se preciso) modalidade-usina e usina_conjunto do cache externo."""
    from coff.download import baixar_arquivo

    pasta = Path(pasta_externo)
    caminhos = {}
    for nome, url in URLS.items():
        destino = pasta / f"{nome}.csv"
        baixar_arquivo(url, destino)
        caminhos[nome] = destino
    modalidade = pd.read_csv(caminhos["modalidade_usina"], sep=";", low_memory=False)
    conjuntos = pd.read_csv(caminhos["usina_conjunto"], sep=";", low_memory=False)
    modalidade["ceg"] = modalidade["ceg"].astype(str).str.strip().str.upper()
    conjuntos["ceg"] = conjuntos["ceg"].astype(str).str.strip().str.upper()
    return modalidade, conjuntos


def _pacs_de_usinas(usinas: pd.DataFrame) -> pd.DataFrame:
    """Agrega usinas (com ``nom_pontoconexao`` e ``val_potenciaautorizada``) por PAC normalizado."""
    u = usinas.copy()
    chaves = [normalizar_pac(v) for v in u["nom_pontoconexao"]]
    u["pac_chave"] = [c for c, _ in chaves]
    u["pac_tensao_kv"] = [t for _, t in chaves]
    u["pot"] = pd.to_numeric(u["val_potenciaautorizada"], errors="coerce").fillna(0.0)
    com = u[u["pac_chave"].notna()]
    if com.empty:
        return pd.DataFrame(columns=["pac_chave", "pac_tensao_kv", "pot_mw", "n_usinas", "grafias"])
    g = com.groupby("pac_chave").agg(
        pac_tensao_kv=(
            "pac_tensao_kv",
            lambda s: s.dropna().mode().iloc[0] if s.notna().any() else None,
        ),
        pot_mw=("pot", "sum"),
        n_usinas=("pot", "size"),
        grafias=("nom_pontoconexao", lambda s: " | ".join(sorted(set(map(str, s))))),
    )
    return g.reset_index().sort_values("pot_mw", ascending=False).reset_index(drop=True)


def construir_mapa(
    usinas_coff: pd.DataFrame, modalidade: pd.DataFrame, conjuntos: pd.DataFrame
) -> pd.DataFrame:
    """Uma linha por (id_ons x PAC).

    ``usinas_coff``: colunas ``id_ons, nom_usina, uf, fonte, ceg``. Regras: conjunto ->
    usinas ativas do ``usina_conjunto`` -> PAC por ``ceg`` na ``modalidade-usina``; PAC unico
    (>= 90 % da potencia) -> ``metodo=ons_cadastro, confianca=alta``; varios PACs ->
    rateio pela potencia (``metodo=rateio_potencia, confianca=media``); usina individual ->
    junção direta por ``ceg``; sem casamento -> PAC nulo (``metodo=nao_casado``).
    """
    mod = modalidade.drop_duplicates("ceg").set_index("ceg")
    conj = conjuntos.copy()
    conj["_fim"] = pd.to_datetime(conj["dat_fimrelacionamento"], errors="coerce")
    por_conjunto = {k: g for k, g in conj.groupby(conj["id_ons_conjunto"].astype(str))}
    linhas = []
    for _, r in usinas_coff.iterrows():
        id_ons = str(r["id_ons"])
        base = {
            "id_ons": id_ons,
            "nom_usina": r["nom_usina"],
            "uf": r["uf"],
            "fonte": r["fonte"],
        }
        membros = por_conjunto.get(id_ons)
        vigencia = "ativo"
        if membros is not None and len(membros):
            ativos = membros[membros["_fim"].isna()]
            if len(ativos):
                membros = ativos
            else:
                # conjunto reorganizado/encerrado: usa a composicao mais recente
                ultimo_fim = membros["_fim"].max()
                membros = membros[membros["_fim"] == ultimo_fim]
                vigencia = f"encerrado em {ultimo_fim.date()}"
        base["vigencia"] = vigencia
        if membros is not None and len(membros):
            u = membros[["ceg"]].merge(
                mod[["nom_pontoconexao", "val_potenciaautorizada"]],
                left_on="ceg",
                right_index=True,
                how="left",
            )
            pacs = _pacs_de_usinas(u)
            n_total = len(u)
            n_sem = int(u["nom_pontoconexao"].isna().sum())
            if pacs.empty:
                linhas.append(
                    {
                        **base,
                        "pac_nome": None,
                        "pac_tensao_kv": None,
                        "fracao_potencia": None,
                        "n_usinas": n_total,
                        "n_usinas_sem_pac": n_sem,
                        "pot_mw": 0.0,
                        "metodo": "nao_casado",
                        "confianca": None,
                        "grafias": None,
                    }
                )
                continue
            total = float(pacs["pot_mw"].sum())
            if total <= 0:
                pacs["fracao"] = 1.0 / len(pacs)
            else:
                pacs["fracao"] = pacs["pot_mw"] / total
            if float(pacs["fracao"].iloc[0]) >= LIMIAR_PAC_UNICO:
                p = pacs.iloc[0]
                linhas.append(
                    {
                        **base,
                        "pac_nome": p["pac_chave"],
                        "pac_tensao_kv": p["pac_tensao_kv"],
                        "fracao_potencia": 1.0,
                        "n_usinas": n_total,
                        "n_usinas_sem_pac": n_sem,
                        "pot_mw": total,
                        "metodo": "ons_cadastro",
                        "confianca": "alta",
                        "grafias": p["grafias"],
                    }
                )
            else:
                for _, p in pacs.iterrows():
                    linhas.append(
                        {
                            **base,
                            "pac_nome": p["pac_chave"],
                            "pac_tensao_kv": p["pac_tensao_kv"],
                            "fracao_potencia": float(p["fracao"]),
                            "n_usinas": n_total,
                            "n_usinas_sem_pac": n_sem,
                            "pot_mw": float(p["pot_mw"]),
                            "metodo": "rateio_potencia",
                            "confianca": "media",
                            "grafias": p["grafias"],
                        }
                    )
            continue
        ceg = str(r.get("ceg", "-")).strip().upper()
        if ceg and ceg != "-" and ceg in mod.index:
            chave, tensao = normalizar_pac(mod.loc[ceg, "nom_pontoconexao"])
            if chave:
                linhas.append(
                    {
                        **base,
                        "pac_nome": chave,
                        "pac_tensao_kv": tensao,
                        "fracao_potencia": 1.0,
                        "n_usinas": 1,
                        "n_usinas_sem_pac": 0,
                        "pot_mw": float(
                            pd.to_numeric(mod.loc[ceg, "val_potenciaautorizada"], errors="coerce")
                            or 0.0
                        ),
                        "metodo": "ons_cadastro",
                        "confianca": "alta",
                        "grafias": str(mod.loc[ceg, "nom_pontoconexao"]),
                    }
                )
                continue
        linhas.append(
            {
                **base,
                "pac_nome": None,
                "pac_tensao_kv": None,
                "fracao_potencia": None,
                "n_usinas": 0,
                "n_usinas_sem_pac": 0,
                "pot_mw": 0.0,
                "metodo": "nao_casado",
                "confianca": None,
                "grafias": None,
            }
        )
    return pd.DataFrame(linhas)


def pacs_distintos(mapa: pd.DataFrame, eng_por_id: pd.Series | None = None) -> pd.DataFrame:
    """Lista de PACs apos normalizacao: nº de usinas/conjuntos, MW, ENG rateada e grafias."""
    m = mapa[mapa["pac_nome"].notna()].copy()
    if eng_por_id is not None:
        m["eng_gwh"] = (
            m["id_ons"].map(eng_por_id).fillna(0.0) * m["fracao_potencia"].fillna(0.0) / 1000
        )
    else:
        m["eng_gwh"] = 0.0
    g = m.groupby("pac_nome").agg(
        pac_tensao_kv=(
            "pac_tensao_kv",
            lambda s: s.dropna().mode().iloc[0] if s.notna().any() else None,
        ),
        conjuntos_usinas=("id_ons", "nunique"),
        usinas_cadastro=("n_usinas", "sum"),
        pot_mw=("pot_mw", "sum"),
        eng_gwh=("eng_gwh", "sum"),
        grafias=(
            "grafias",
            lambda s: " | ".join(sorted({x for v in s.dropna() for x in str(v).split(" | ")})),
        ),
    )
    return g.reset_index().sort_values("eng_gwh", ascending=False).reset_index(drop=True)
