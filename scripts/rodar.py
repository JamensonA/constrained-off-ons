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

from coff import carregar, download, figuras, metricas, qualificar  # noqa: E402

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
    log.info("metricas: 5 figuras em docs/figuras, CSVs e tabela de sensibilidade em docs/")


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
