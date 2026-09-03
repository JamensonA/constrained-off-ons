"""Etapa 4 do cruzamento por ponto de conexao: barramentos da NT 02 x usinas do mapa.

Entradas: ``nt02_barramentos_geracao.csv`` (Etapa 2), ``mapa_usina_pac.csv`` (Etapa 3),
``nt02_siglas_pac.csv`` (sigla da NT -> nome do PAC, transcrita pelo autor) e
``adjacencia_pac.csv`` (PACs eletricamente adjacentes, gerada por regras e revisada a mao).
"""

from __future__ import annotations

import re

import pandas as pd

from coff import descricoes
from coff.pac import normalizar_pac

RELACOES_USADAS = ("mesmo", "icg", "seccionamento", "homonimo")


def chaves_das_siglas(siglas: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta ``pac_chave`` (nome normalizado) a tabela sigla -> nome."""
    t = siglas.copy()
    t["pac_chave"] = [normalizar_pac(n)[0] for n in t["nome_pac"]]
    return t


def _se_do_icg(chave: str) -> str | None:
    return chave[: -len(" ICG")] if chave.endswith(" ICG") else None


def _par_do_seccionamento(chave: str) -> tuple[str, str] | None:
    m = re.match(r"SECC\. L[TD] (.+?) – (.+)$", chave)
    return (m.group(1), m.group(2)) if m else None


def gerar_adjacencias(
    chaves_mapa: set[str], siglas: pd.DataFrame
) -> tuple[pd.DataFrame, list[str]]:
    """Adjacencias por regra: mesmo PAC, ICG <-> SE, seccionamento <-> as duas SEs, homonimos.

    Devolve (tabela, siglas_sem_correspondente). Colunas: ``sigla, pac_barramento,
    pac_adjacente, relacao, origem``.
    """
    t = chaves_das_siglas(siglas)
    linhas = []
    faltantes = []
    for _, r in t.iterrows():
        chave = r["pac_chave"]
        if chave not in chaves_mapa:
            faltantes.append(f"{r['sigla']} = {r['nome_pac']} -> chave '{chave}' nao esta no mapa")
        linhas.append(
            {
                "sigla": r["sigla"],
                "pac_barramento": chave,
                "pac_adjacente": chave,
                "relacao": "mesmo",
                "origem": "regra",
            }
        )
        for k in sorted(chaves_mapa):
            if k == chave:
                continue
            if _se_do_icg(k) == chave:
                linhas.append(
                    {
                        "sigla": r["sigla"],
                        "pac_barramento": chave,
                        "pac_adjacente": k,
                        "relacao": "icg",
                        "origem": "regra",
                    }
                )
            par = _par_do_seccionamento(k)
            if par and chave in par:
                linhas.append(
                    {
                        "sigla": r["sigla"],
                        "pac_barramento": chave,
                        "pac_adjacente": k,
                        "relacao": "seccionamento",
                        "origem": "regra",
                    }
                )
        # homonimos decididos pelo autor: Queimada Nova <-> Queimada Nova 2; SVP <-> SVP 2
        for a, b in (
            ("QUEIMADA NOVA", "QUEIMADA NOVA 2"),
            ("SANTA VITORIA DO PALMAR", "SANTA VITORIA DO PALMAR 2"),
        ):
            outro = b if chave == a else a if chave == b else None
            if outro and outro in chaves_mapa:
                linhas.append(
                    {
                        "sigla": r["sigla"],
                        "pac_barramento": chave,
                        "pac_adjacente": outro,
                        "relacao": "homonimo",
                        "origem": "regra",
                    }
                )
    tab = pd.DataFrame(linhas).drop_duplicates().reset_index(drop=True)
    return tab, faltantes


def propor_adjacencias(
    cruz_desc: pd.DataFrame, siglas: pd.DataFrame, chaves_mapa: set[str]
) -> pd.DataFrame:
    """Propostas (nao aplicadas): PACs citados no mesmo elemento de rede das descricoes.

    Para cada elemento "LT X / Y" das descricoes de corte, X e Y viram candidatos a
    adjacencia do barramento cujo PAC e X ou Y (mesmo corredor). ``cruz_desc`` e a tabela
    ``eng_por_descricao``.
    """
    t = chaves_das_siglas(siglas)
    por_chave = dict(zip(t["pac_chave"], t["sigla"], strict=True))
    linhas = []
    for _, d in cruz_desc.iterrows():
        el = str(d.get("elemento") or "")
        if not el.upper().startswith(("LT", "LTS")):
            continue
        corpo = re.sub(r"^LTS?\s+\d+\s*KV\s+", "", el, flags=re.I)
        nomes = [
            normalizar_pac("SE " + p.strip())[0]
            for p in re.split(r"\s*/\s*|\s+E\s+|,", corpo)
            if p.strip()
        ]
        nomes = [n for n in nomes if n]
        for a in nomes:
            if a in por_chave:
                for b in nomes:
                    if b != a and b in chaves_mapa:
                        linhas.append(
                            {
                                "sigla": por_chave[a],
                                "pac_barramento": a,
                                "pac_adjacente": b,
                                "relacao": "corredor",
                                "origem": f"descricao: {el}",
                                "eng_gwh_descricao": round(float(d["eng_gwh"]), 1),
                            }
                        )
    # extremos dos seccionamentos que tocam o PAC do barramento (mesmo corredor) e seus ICG
    for chave_b, sigla in por_chave.items():
        for k in chaves_mapa:
            par = _par_do_seccionamento(k)
            if not par or chave_b not in par:
                continue
            outro = par[1] if par[0] == chave_b else par[0]
            if outro in chaves_mapa and outro != chave_b:
                linhas.append(
                    {
                        "sigla": sigla,
                        "pac_barramento": chave_b,
                        "pac_adjacente": outro,
                        "relacao": "corredor",
                        "origem": f"seccionamento: {k}",
                        "eng_gwh_descricao": None,
                    }
                )
            for k2 in chaves_mapa:
                if k2.endswith(" ICG") and k2[:-4] == outro:
                    linhas.append(
                        {
                            "sigla": sigla,
                            "pac_barramento": chave_b,
                            "pac_adjacente": k2,
                            "relacao": "corredor",
                            "origem": f"ICG de {outro}",
                            "eng_gwh_descricao": None,
                        }
                    )
    if not linhas:
        return pd.DataFrame(
            columns=[
                "sigla",
                "pac_barramento",
                "pac_adjacente",
                "relacao",
                "origem",
                "eng_gwh_descricao",
            ]
        )
    return pd.DataFrame(linhas).drop_duplicates(["sigla", "pac_adjacente"]).reset_index(drop=True)


def _eng_por_usina_e_classe(
    q: pd.DataFrame, desde: str = "2025-09"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Por id_ons: ENG de rede por classe_efetiva e por descricao normalizada (desde 2025-09)."""
    mes = q["din_instante"].dt.to_period("M").astype(str)
    r = q[
        q["qualificado"] & (mes >= desde) & q["categoria"].isin(["confiabilidade", "eletrica"])
    ].copy()
    brutas = r["dsc_restricao"].astype("string").fillna("")
    cache: dict[str, descricoes.Descricao] = {}
    normal, classes, elementos = [], [], []
    for b in brutas:
        if b not in cache:
            cache[b] = descricoes.analisar(b)
        d = cache[b]
        normal.append(d.normalizada or "(sem descricao)")
        elementos.append(d.elemento or "")
        classes.append(d.classe)
    r["descricao"] = normal
    r["elemento"] = elementos
    r["classe"] = classes
    r["origem_txt"] = r["origem"].astype("string").fillna("desconhecida")
    r["classe_efetiva"] = [
        descricoes.classe_efetiva(c, o) for c, o in zip(r["classe"], r["origem_txt"], strict=True)
    ]
    por_classe = (
        r.groupby([r["id_ons"].astype(str), "classe_efetiva"], observed=True)["eng_mwh"]
        .sum()
        .unstack(fill_value=0.0)
    )
    por_desc = (
        r.groupby([r["id_ons"].astype(str), "descricao", "elemento"], observed=True)["eng_mwh"]
        .sum()
        .reset_index()
    )
    return por_classe, por_desc


def cruzar_barramentos(
    q: pd.DataFrame,
    mapa: pd.DataFrame,
    adjacencia: pd.DataFrame,
    nt02: pd.DataFrame,
    siglas: pd.DataFrame,
) -> pd.DataFrame:
    """Uma linha por barramento da NT 02 com ENG, categorias, taxa, descricoes e coincidencia."""
    mes = q["din_instante"].dt.to_period("M").astype(str)
    q25 = q[mes >= "2025-01"]
    ids = q25["id_ons"].astype(str)
    eng_id = q25.groupby(ids, observed=True)["eng_mwh"].sum()
    ger_id = q25.groupby(ids, observed=True)["energia_gerada_mwh"].sum()
    eng_cat = (
        q25.groupby([ids, q25["categoria"].astype(str)], observed=True)["eng_mwh"]
        .sum()
        .unstack(fill_value=0.0)
    )
    por_classe, por_desc = _eng_por_usina_e_classe(q)
    t = chaves_das_siglas(siglas).set_index("sigla")
    adj = adjacencia[adjacencia["relacao"].isin(RELACOES_USADAS)]
    m = mapa[mapa["pac_nome"].notna()].copy()
    m["fracao_potencia"] = m["fracao_potencia"].fillna(1.0)
    linhas = []
    for _, b in nt02.iterrows():
        sigla = str(b["sigla"])
        chave = t["pac_chave"].get(sigla) if sigla in t.index else None
        pacs = set(adj.loc[adj["sigla"] == sigla, "pac_adjacente"]) | ({chave} if chave else set())
        sel = m[m["pac_nome"].isin(pacs)]
        pesos = sel.groupby("id_ons")["fracao_potencia"].sum()
        eng = float(sum(eng_id.get(i, 0.0) * w for i, w in pesos.items()))
        ger = float(sum(ger_id.get(i, 0.0) * w for i, w in pesos.items()))
        cats = {
            c: float(
                sum(
                    eng_cat.get(c, pd.Series(dtype=float)).get(i, 0.0) * w for i, w in pesos.items()
                )
            )
            for c in ("energetica", "confiabilidade", "eletrica")
        }
        rede_classe = {}
        for i, w in pesos.items():
            if i in por_classe.index:
                for c, v in por_classe.loc[i].items():
                    rede_classe[c] = rede_classe.get(c, 0.0) + float(v) * w
        total_rede = sum(rede_classe.values())
        frac_exp = (
            (
                rede_classe.get("intercâmbio nomeado", 0.0)
                + rede_classe.get("corredor de exportação", 0.0)
            )
            / total_rede
            if total_rede > 0
            else float("nan")
        )
        descs = por_desc[por_desc["id_ons"].isin(pesos.index)].copy()
        descs["eng"] = descs["eng_mwh"] * descs["id_ons"].map(pesos)
        top_desc = (
            descs.groupby(["descricao", "elemento"])["eng"]
            .sum()
            .sort_values(ascending=False)
            .head(3)
        )
        top_txt = " | ".join(f"{d[:70]} ({v / 1000:.0f} GWh)" for (d, _), v in top_desc.items())
        elementos_desc = {e for (_, e) in top_desc.index if e} | set(
            descs["elemento"][descs["elemento"] != ""]
        )
        # coincidencia
        cond = []
        ne = str(b["uf"]) in {"BA", "SE", "AL", "PE", "PB", "RN", "CE", "PI", "MA"}
        fator = str(b["fator_limitante"] or "")
        if ne:
            if str(b["resultado"]) == "INAB" and total_rede > 0 and frac_exp > 0.5:
                cond.append(
                    "A: INAB e ENG de rede majoritaria em intercâmbio/corredor de exportação"
                )
            nomes_corredor: set[str] = set()
            for n in ({chave} | set(pacs)) if chave else set(pacs):
                if not n:
                    continue
                par = _par_do_seccionamento(n)
                if par:
                    nomes_corredor.update(par)
                else:
                    nomes_corredor.add(re.sub(r" ICG$", "", n))
            citados = [
                e
                for e in elementos_desc
                if any(
                    n and n.lower() in normalizar_pac("SE " + e)[0].lower()
                    if normalizar_pac("SE " + e)[0]
                    else False
                    for n in nomes_corredor
                )
            ]
            if citados:
                cond.append(
                    "B: descrições nomeiam elemento local do corredor ("
                    + "; ".join(sorted(citados))[:120]
                    + ")"
                )
        else:
            citados_nt = str(b.get("elementos_citados") or "")
            alvo = normalizar_pac("SE " + citados_nt)[0] if citados_nt else None
            if alvo and any(
                alvo.split()[0] in normalizar_pac("SE " + e)[0]
                for e in elementos_desc
                if normalizar_pac("SE " + e)[0]
            ):
                cond.append("C: elemento do fator limitante da NT aparece nas descrições de corte")
        linhas.append(
            {
                "sigla": sigla,
                "uf": b["uf"],
                "barramento": b["barramento"],
                "pac_chave": chave,
                "pacs_considerados": "; ".join(sorted(p for p in pacs if p)),
                "resultado": b["resultado"],
                "fator_limitante": fator[:90],
                "n_usinas": int(len(pesos)),
                "eng_gwh": eng / 1000,
                "eng_energetica_gwh": cats["energetica"] / 1000,
                "eng_confiabilidade_gwh": cats["confiabilidade"] / 1000,
                "eng_eletrica_gwh": cats["eletrica"] / 1000,
                "energia_gerada_gwh": ger / 1000,
                "taxa_corte": eng / (eng + ger) if eng + ger > 0 else float("nan"),
                "frac_rede_exportacao": frac_exp,
                "top3_descricoes": top_txt,
                "coincidencia": bool(cond),
                "condicao": " / ".join(cond) if cond else "",
            }
        )
    return pd.DataFrame(linhas).sort_values("eng_gwh", ascending=False).reset_index(drop=True)
