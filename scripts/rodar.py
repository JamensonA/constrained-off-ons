"""Pipeline ponta a ponta: baixar -> carregar -> (qualificar -> metricas -> figuras).

Uso: ``python scripts/rodar.py --desde 2023-01``. Etapas posteriores ao Gate 1
sao acrescentadas nos gates seguintes.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import datetime as dt  # noqa: E402

import pandas as pd  # noqa: E402

from coff import carregar, descricoes, download, figuras, metricas, qualificar  # noqa: E402

log = logging.getLogger("coff")


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--desde", default="2023-01", help="primeiro mes (AAAA-MM)")
    p.add_argument("--ate", default=None, help="ultimo mes (AAAA-MM); padrao: ultimo publicado")
    p.add_argument("--fontes", default="EOL,UFV", help="lista separada por virgula: EOL,UFV")
    p.add_argument(
        "--referencia",
        choices=("coalesce", "referencia"),
        default="coalesce",
        help="referencia efetiva (R6): coalesce(final, referencia) ou so referencia",
    )
    p.add_argument("--forcar", action="store_true", help="rebaixa arquivos ja em cache")
    p.add_argument("--excluir-disp-zero", action="store_true", help="R10 opcional")
    p.add_argument("--dados", default=str(RAIZ / "data"), help="pasta de dados (gitignored)")
    p.add_argument("--docs", default=str(RAIZ / "docs"), help="pasta de saida de docs")
    p.add_argument("--sem-download", action="store_true", help="usa apenas o cache local")
    return p.parse_args(argv)


def etapa_download(args: argparse.Namespace) -> None:
    pasta_raw = Path(args.dados) / "raw"
    fontes = tuple(f.strip().upper() for f in args.fontes.split(","))
    res = download.baixar_janela(pasta_raw, fontes, args.desde, args.ate, args.forcar)
    for fonte, itens in res.items():
        novos = sum(1 for _, _, b in itens if b)
        log.info("%s: %d meses (%d baixados agora)", fonte, len(itens), novos)
    download.gerar_dicionario_md(pasta_raw, Path(args.docs) / "dicionario.md")


def etapa_carga(args: argparse.Namespace):
    pasta_raw = Path(args.dados) / "raw"
    fontes = tuple(f.strip().upper() for f in args.fontes.split(","))
    df, rel = carregar.carregar(
        pasta_raw,
        fontes,
        download.normalizar_periodo(args.desde),
        download.normalizar_periodo(args.ate),
    )
    processado = Path(args.dados) / "processed"
    processado.mkdir(parents=True, exist_ok=True)
    df.to_parquet(processado / "agregado.parquet", index=False)
    texto = carregar.relatorio_markdown(rel, "Relatorio de carga (Gate 1)")
    (Path(args.docs) / "relatorio_carga.md").write_text(texto, encoding="utf-8")
    log.info("carga: %s linhas; relatorio em docs/relatorio_carga.md", f"{len(df):,}")
    return df, rel


def etapa_qualificacao(args: argparse.Namespace, df, rel_carga):
    delta_t_h = min(rel_carga.delta_t.values()).total_seconds() / 3600
    q = qualificar.qualificar(df, args.referencia, delta_t_h, args.excluir_disp_zero)
    # o resultado qualificado nao e persistido (recalculado em memoria a cada execucao)
    rel = qualificar.relatorio_qualificacao(q, args.referencia, delta_t_h)
    (Path(args.docs) / "relatorio_qualificacao.md").write_text(
        qualificar.relatorio_markdown(rel), encoding="utf-8"
    )
    log.info(
        "qualificacao: %s qualificados de %s; ENG total %.0f MWh; relatorio em "
        "docs/relatorio_qualificacao.md",
        f"{int(q['qualificado'].sum()):,}",
        f"{len(q):,}",
        q["eng_mwh"].sum(),
    )
    return q, rel


def _tabela_md(tab) -> str:
    cols = list(tab.columns)
    linhas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in tab.iterrows():
        linhas.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(linhas)


def _substituir_bloco(caminho: Path, marca: str, conteudo: str) -> None:
    """Substitui o texto entre ``<!-- marca:inicio -->`` e ``<!-- marca:fim -->``."""
    ini, fim = f"<!-- {marca}:inicio -->", f"<!-- {marca}:fim -->"
    texto = caminho.read_text(encoding="utf-8")
    if ini not in texto or fim not in texto:
        texto = texto.rstrip() + f"\n\n{ini}\n{fim}\n"
    a, b = texto.index(ini) + len(ini), texto.index(fim)
    caminho.write_text(texto[:a] + "\n" + conteudo.strip() + "\n" + texto[b:], encoding="utf-8")


def etapa_metricas(args: argparse.Namespace, q, rel_carga, delta_t_h: float) -> None:
    docs = Path(args.docs)
    pasta_fig = docs / "figuras"
    data_download = max(a.caminho.stat().st_mtime for a in rel_carga.arquivos)
    rodape = (
        "Fonte: ONS, Portal de Dados Abertos (restricao_coff_eolica_usi, "
        "restricao_coff_fotovoltaica); download em "
        f"{dt.datetime.fromtimestamp(data_download):%Y-%m-%d}; referencia: {args.referencia}"
    )
    t_mes = metricas.eng_por_mes(q)
    t_cat = metricas.eng_por_categoria(q)
    t_sub = metricas.eng_por_subsistema(q)
    t_top = metricas.top_usinas(q, 15)
    t_perfil = metricas.perfil_hora_mes(q)
    t_dsc = metricas.top_descricoes(q, 20)
    t_sens = metricas.sensibilidade_referencia(q, delta_t_h)
    t_par = metricas.ocorrencias_par(q)
    t_anual = metricas.resumo_anual(q)

    figuras.fig1_eng_mensal(t_mes, pasta_fig / "fig1_eng_mensal.png", rodape)
    figuras.fig2_eng_por_categoria(t_cat, pasta_fig / "fig2_eng_por_categoria.png", rodape)
    figuras.fig3_top_usinas(t_top, pasta_fig / "fig3_top_usinas.png", rodape)
    figuras.fig4_perfil_hora_mes(t_perfil, pasta_fig / "fig4_perfil_hora_mes.png", rodape)
    figuras.fig5_top_descricoes(t_dsc, pasta_fig / "fig5_top_descricoes.png", rodape, 15)

    t_anual.round(2).to_csv(docs / "resumo_anual.csv", index=False)
    t_dsc.round(1).to_csv(docs / "top_descricoes.csv", index=False)
    t_sens.round(4).to_csv(docs / "sensibilidade_referencia.csv", index=False)
    t_sub.round(1).to_csv(docs / "eng_por_subsistema.csv", index=False)
    t_top.round(4).to_csv(docs / "top_usinas.csv", index=False)

    sens = t_sens.copy()
    for c in ("eng_coalesce_mwh", "eng_referencia_mwh", "dif_abs_mwh"):
        sens[c] = (sens[c] / 1000).round(1)
    sens["dif_rel"] = (100 * sens["dif_rel"]).round(2)
    sens.columns = [
        "fonte",
        "categoria",
        "ENG coalesce (GWh)",
        "ENG referencia (GWh)",
        "dif (GWh)",
        "dif (%)",
    ]
    par_txt = (
        "Nenhuma ocorrencia do codigo PAR na janela." if t_par.empty else _tabela_md(t_par.round(1))
    )
    _substituir_bloco(
        docs / "metodologia.md",
        "sensibilidade",
        "Tabela de sensibilidade (R6): ENG por fonte e categoria com referencia efetiva "
        "`coalesce(final, referencia)` versus apenas `referencia`, sobre os registros "
        "qualificados de toda a janela.\n\n"
        + _tabela_md(sens)
        + "\n\nOcorrencias de PAR: "
        + par_txt,
    )
    _substituir_bloco(docs / "metodologia.md", "resumo_anual", _tabela_md(t_anual.round(2)))
    etapa_validacao_externa(docs, q, t_cat)
    etapa_temporada(docs, q, rodape, args)
    etapa_descricoes(docs, q)
    log.info("metricas: 8 figuras em docs/figuras, CSVs e tabela de sensibilidade em docs/")


def etapa_temporada(docs: Path, q, rodape: str, args: argparse.Namespace | None = None) -> None:
    """Cruzamento ENG por UF (2025-01 -> ultimo mes) x 1a Temporada de Acesso 2026 (NT 02)."""
    import pandas as pd

    eng_uf = metricas.eng_por_uf(q, "2025-01")
    eng_uf.round(4).to_csv(docs / "eng_por_uf.csv", index=False)
    temporada = pd.read_csv(docs / "temporada_acesso_2026_nt02.csv")
    cruz = metricas.cruzar_temporada(eng_uf, temporada)
    cruz.round(4).to_csv(docs / "cruzamento_temporada.csv", index=False)
    rho, n = metricas.spearman_taxa_inabilitacao(cruz)
    rodape2 = (
        "Fonte: ONS, Portal de Dados Abertos (restricao_coff_eolica_usi, "
        "restricao_coff_fotovoltaica); referência: "
        + (args.referencia if args else "coalesce")
        + "  |  Temporada: ONS, NT-ONS DPL 0083/2026 (1ª Temporada de Acesso 2026), "
        "infográfico, extrato de 01/09/2026"
    )
    figuras.fig6_temporada_x_eng(cruz, docs / "figuras" / "fig6_temporada_x_eng.png", rodape2)
    figuras.fig7_taxa_corte_x_inabilitacao(
        cruz, docs / "figuras" / "fig7_taxa_corte_x_inabilitacao.png", rodape2, rho, n
    )
    tab = cruz[
        [
            "uf",
            "eng_gwh",
            "energia_gerada_gwh",
            "taxa_corte",
            "cadastrado_mw",
            "inab_mw",
            "frac_inab",
        ]
    ].copy()
    tab["taxa_corte"] = (100 * tab["taxa_corte"]).round(1)
    tab["frac_inab"] = (100 * tab["frac_inab"]).round(1)
    tab = tab.round(1)
    tab.columns = [
        "UF",
        "ENG (GWh)",
        "gerada (GWh)",
        "taxa (%)",
        "cadastrado (MW)",
        "INAB (MW)",
        "INAB (%)",
    ]
    _substituir_bloco(
        docs / "metodologia.md",
        "temporada",
        f"Spearman(taxa de corte, fracao inabilitada) = **{rho:.2f}** "
        f"(n = {n} UFs com os dois dados).\n\n" + _tabela_md(tab),
    )
    log.info("temporada: Spearman = %.3f (n = %d)", rho, n)
    etapa_por_razao(docs, eng_uf, temporada, rodape2)


def etapa_descricoes(docs: Path, q) -> None:
    """Etapa 1 do cruzamento por PAC: ENG por descricao normalizada e por elemento (NE)."""
    tab = descricoes.tabela_descricoes(q, "2025-09")
    tab.round(4).to_csv(docs / "eng_por_descricao.csv", index=False)
    por_el, resumo = descricoes.eng_rede_ne_por_elemento(q, "2025-09")
    por_el.round(4).to_csv(docs / "eng_cnf_ne_por_elemento.csv", index=False)
    top = tab.head(20)[
        [
            "descricao",
            "tipo",
            "elemento",
            "classe",
            "categoria_principal",
            "origem_principal",
            "eng_gwh",
            "usinas",
            "meses",
        ]
    ].copy()
    top["descricao"] = top["descricao"].str.slice(0, 90)
    top["eng_gwh"] = top["eng_gwh"].round(1)
    top.columns = [
        "descrição",
        "tipo",
        "elemento",
        "classe",
        "categoria",
        "origem",
        "ENG (GWh)",
        "usinas",
        "meses",
    ]
    res = resumo.copy()
    res["eng_gwh"] = res["eng_gwh"].round(1)
    res["fracao"] = (100 * res["fracao"]).round(1)
    res.columns = ["classe efetiva", "ENG (GWh)", "fração (%)"]
    texto = (
        f"Descricoes distintas apos normalizacao: {len(tab)} "
        "(registros qualificados desde 2025-09).\n\n"
        "**20 maiores descricoes por ENG**\n\n" + "\n".join(_tabela_md(top)) + "\n\n"
        "**ENG de rede (CNF + REL) no Nordeste por classe de elemento**\n\n"
        + "\n".join(_tabela_md(res))
    )
    _substituir_bloco(docs / "metodologia.md", "descricoes", texto)
    log.info("descricoes: %d distintas; NE rede: %s", len(tab), res.to_dict("records"))


TITULO_FIG8 = "Na escala de UF, nem o corte de rede se correlaciona com a inabilitação (n = 10)"


def etapa_por_razao(docs: Path, eng_uf, temporada, rodape2: str) -> None:
    """Teste fino: fracao inabilitada x taxa de corte por razao (CNF+REL vs ENE)."""
    taxas = metricas.taxas_por_razao_uf(eng_uf)
    cruz = metricas.cruzar_por_razao(taxas, temporada)
    cruz.round(4).to_csv(docs / "cruzamento_por_razao.csv", index=False)
    completa = metricas.tabela_correlacoes(cruz)
    completa["amostra"] = "todas as UFs com os dois dados"
    sem_go = metricas.tabela_correlacoes(cruz, excluir=("GO",))
    sem_go["amostra"] = "sem GO (140 MW, 100 % inabilitado)"
    tabela = pd.concat([completa, sem_go], ignore_index=True)
    tabela.round(4).to_csv(docs / "correlacoes_por_razao.csv", index=False)
    rho_rede_sem_go = float(sem_go.set_index("metrica").loc["taxa_rede", "rho"])
    p_rede_sem_go = float(sem_go.set_index("metrica").loc["taxa_rede", "p"])
    nota = (
        f"GO: 140 MW, 100 % inabilitado; sem GO, ρ (rede) = {rho_rede_sem_go:.2f} "
        f"e p = {p_rede_sem_go:.2f}"
    ).replace(".", ",")
    figuras.fig8_inabilitacao_por_razao(
        cruz,
        docs / "figuras" / "fig8_inabilitacao_por_razao.png",
        rodape2,
        completa,
        TITULO_FIG8,
        "GO",
        nota,
    )
    md = tabela.copy()
    md["rho"] = md["rho"].round(3)
    md["p"] = md["p"].round(4)
    md = md[["amostra", "metrica", "rho", "p", "n", "metodo"]]
    md.columns = ["amostra", "métrica", "ρ", "p", "n", "método"]
    _substituir_bloco(docs / "metodologia.md", "por_razao", _tabela_md(md))
    log.info(
        "por razao: rede rho=%.3f p=%.3f | ene rho=%.3f p=%.3f (n=%d)",
        float(completa.loc[2, "rho"]),
        float(completa.loc[2, "p"]),
        float(completa.loc[1, "rho"]),
        float(completa.loc[1, "p"]),
        int(completa.loc[2, "n"]),
    )


def etapa_validacao_externa(docs: Path, q, t_cat) -> None:
    """Compara a taxa de corte mensal e a ENG energetica de 2024 com numeros publicados pelo ONS.

    Serie do ONS transcrita em ``docs/validacao_ons_serie.csv`` (% do potencial de geracao,
    eolica + fotovoltaica); ENE 2024 = 4.330 GWh (RT DGL-ONS 0189/2025, secao 4.2).
    """
    import pandas as pd

    serie = pd.read_csv(docs / "validacao_ons_serie.csv")
    nossa = metricas.taxa_mensal(q)
    comp = nossa.merge(serie[["mes", "pct_ons"]], on="mes", how="inner")
    comp["pct_repo"] = 100 * comp["taxa_corte"]
    comp["dif_pp"] = comp["pct_repo"] - comp["pct_ons"]
    saida = comp[["mes", "eng_mwh", "energia_gerada_mwh", "pct_repo", "pct_ons", "dif_pp"]].round(2)
    saida.to_csv(docs / "validacao_externa.csv", index=False)

    ene_2024_gwh = (
        t_cat[(t_cat["mes"].str.startswith("2024")) & (t_cat["categoria"] == "energetica")][
            "eng_mwh"
        ].sum()
        / 1000
    )
    ons_ene_2024 = 4330.0
    n = len(comp)
    corr = comp["pct_repo"].corr(comp["pct_ons"]) if n > 2 else float("nan")
    mae = comp["dif_pp"].abs().mean()
    vies = comp["dif_pp"].mean()
    tab = saida.copy()
    tab.columns = [
        "mes",
        "ENG (MWh)",
        "energia gerada (MWh)",
        "taxa repo (%)",
        "taxa ONS (%)",
        "dif (p.p.)",
    ]
    texto = (
        "Duas referencias publicadas pelo ONS foram encontradas e comparadas com o resultado do "
        "pipeline (referencia `coalesce`, todos os registros qualificados):\n\n"
        "1. **RT DGL-ONS 0189/2025 (GT Cortes de Geracao, secao 4.2)**: restricoes por razao "
        f"energetica em 2024 = **4.330 GWh**. Este repositorio: **{ene_2024_gwh:,.0f} GWh** "
        f"(diferenca {ene_2024_gwh - ons_ene_2024:+,.0f} GWh, "
        f"{100 * (ene_2024_gwh / ons_ene_2024 - 1):+.1f} %).\n"
        '2. **Serie mensal "Geracao Nao Realizada (Apurada), eolica + fotovoltaica, '
        '% do potencial de geracao"** (apresentacao do ONS no XXXI Simposio Juridico da ABCE, '
        "out/2025; a parte de 2023 "
        "coincide com a Fig. 4-3 do RT acima), transcrita em `validacao_ons_serie.csv`. "
        f"Comparacao em {n} meses (2023-01 a 2025-09): correlacao {corr:.3f}, erro absoluto medio "
        f"{mae:.2f} p.p., vies {vies:+.2f} p.p. Tabela completa em `validacao_externa.csv`.\n\n"
        + _tabela_md(tab)
        + "\n\nLeitura: o ONS publica percentuais apurados (com regras da REN ANEEL 1.030/2022 e "
        "reconsistencias) e nao a serie bruta; diferencas de alguns pontos percentuais sao "
        "esperadas. "
        "Nao foi encontrado um total mensal em GWh publicado pelo ONS por fonte."
    )
    _substituir_bloco(docs / "metodologia.md", "validacao", texto)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = argumentos(argv)
    if not args.sem_download:
        etapa_download(args)
    df, rel_carga = etapa_carga(args)
    q, _ = etapa_qualificacao(args, df, rel_carga)
    del df
    delta_t_h = min(rel_carga.delta_t.values()).total_seconds() / 3600
    etapa_metricas(args, q, rel_carga, delta_t_h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
