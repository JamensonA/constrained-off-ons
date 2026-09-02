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

from coff import carregar, download, qualificar  # noqa: E402

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
    processado = Path(args.dados) / "processed"
    q.to_parquet(processado / "qualificado.parquet", index=False)
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


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = argumentos(argv)
    if not args.sem_download:
        etapa_download(args)
    df, rel_carga = etapa_carga(args)
    etapa_qualificacao(args, df, rel_carga)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
