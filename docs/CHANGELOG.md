# CHANGELOG (uma linha por gate)

- G0 (2026-09-02): estrutura do repositorio, pyproject, .gitignore, LICENSE (MIT), README esqueleto, primeiro commit.
- G1 (2026-09-02): download via API CKAN (parquet com fallback CSV, cache, paralelo), carga tipada com validacao de schema (ausencia de dsc_restricao tolerada e reportada), delta t inferido, tabela codigo->categoria, docs/dicionario.md gerado do JSON do portal, docs/relatorio_carga.md, testes de carga.
- G2 (2026-09-02): qualificar.py (R1–R12), 15 testes sobre a fixture da secao 6, docs/relatorio_qualificacao.md (contagens por motivo e flag, fonte x ano), docs/metodologia.md (regras + limitacoes); repo movido para ~/Projetos.
- G3 (2026-09-02): metricas.py (funcoes 1-8 + resumo anual + taxa mensal), figuras.py (5 figuras), rodar.py ponta a ponta, CSVs em docs/, tabela de sensibilidade coalesce x referencia, validacao externa contra RT DGL-ONS 0189/2025 e serie mensal apurada do ONS; qualificado nao e mais persistido em disco.
- G4 (2026-09-02): README completo com textos do autor, notebook 01_exploracao.ipynb, metodologia final, checklist da secao 9; figura 5 sem a barra "(sem descricao)".
- Extra (2026-09-02): cruzamento com a 1a Temporada de Acesso 2026 (NT-ONS DPL 0083/2026): eng_por_uf, cruzar_temporada, figuras 6 e 7, CSVs e secao na metodologia/README.
- Extra (2026-09-02): teste fino inabilitacao x taxa de corte por razao (CNF+REL vs ENE): taxas por UF com denominador comum, Spearman com p por permutacao, sensibilidade sem GO, figura 8, CSVs e secao na metodologia.
- Extra (2026-09-02): Etapa 1 do cruzamento por PAC: parser de dsc_restricao (descricoes.py), eng_por_descricao.csv e eng_cnf_ne_por_elemento.csv com classe e classe_efetiva.
- Extra (2026-09-02): Etapa 2 do cruzamento por PAC: extracao da NT-ONS DPL 0083/2026 (nt02.py, scripts/extrair_nt02.py), nt02_barramentos_geracao.csv, validacao do INAB por UF (BA: NT prevalece, 4.659,7 MW), figuras 6-8 regeradas.
- Extra (2026-09-02): Etapa 3 do cruzamento por PAC: mapa usina/conjunto -> ponto de conexao (pac.py) a partir de modalidade-usina + usina_conjunto, com normalizacao de grafias, rateio por potencia, mapa_usina_pac.csv e pacs_distintos.csv.
