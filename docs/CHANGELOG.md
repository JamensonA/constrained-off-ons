# CHANGELOG (uma linha por gate)

- G0 (2026-09-02): estrutura do repositorio, pyproject, .gitignore, LICENSE (MIT), README esqueleto, primeiro commit.
- G1 (2026-09-02): download via API CKAN (parquet com fallback CSV, cache, paralelo), carga tipada com validacao de schema (ausencia de dsc_restricao tolerada e reportada), delta t inferido, tabela codigo->categoria, docs/dicionario.md gerado do JSON do portal, docs/relatorio_carga.md, testes de carga.
- G2 (2026-09-02): qualificar.py (R1–R12), 15 testes sobre a fixture da secao 6, docs/relatorio_qualificacao.md (contagens por motivo e flag, fonte x ano), docs/metodologia.md (regras + limitacoes); repo movido para ~/Projetos.
