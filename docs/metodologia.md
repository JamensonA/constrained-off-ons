# Metodologia

Documento vivo, preenchido gate a gate (G1 carga, G2 qualificacao, G3 metricas e sensibilidade, G4 validacao externa).

## Fontes e janela

- Portal de dados abertos do ONS, pacotes CKAN `restricao_coff_eolica_usi` (EOL) e `restricao_coff_fotovoltaica` (UFV): dados **agregados por usina/conjunto**, semi-horarios (delta t = 30 min, inferido e verificado na carga).
- Download dos dados: 2026-09-02 (data registrada aqui; as figuras 6 e 7 nao a repetem no rodape).
- Janela: 2023-01 ate o ultimo mes publicado (EOL 2023_01→2026_08, 44 meses; UFV 2024_04→2026_08, 29 meses). Detalhes em `relatorio_carga.md`.

## Qualificacao (regras R1–R12)

Implementadas em `src/coff/qualificar.py` exatamente como escritas na spec v2, secao 4. Nenhuma linha e descartada. Cada registro recebe `restrito`, `qualificado`, `motivo` (o primeiro que falhar, na ordem abaixo) e flags informativas. As contagens completas, por fonte e por ano, estao em `relatorio_qualificacao.md` (gerado por `scripts/rodar.py`).

| regra | criterio | efeito |
|---|---|---|
| R1 | `restrito` = codigo de razao nao nulo | nao restrito -> `motivo=sem_restricao`; a linha fica para a energia gerada |
| R2 | codigo (strip, upper) em {ENE, CNF, REL, PAR} | fora disso -> `motivo=codigo_desconhecido`, contado por valor |
| R3 | origem em {LOC, SIS} | outro/nulo -> flag `origem_desconhecida`, linha mantida |
| R4 | `din_instante` parseavel; unicidade por (`id_ons`, `din_instante`) | invalido -> `motivo=instante_invalido`; duplicata -> mantem a ultima, as demais `motivo=duplicata` |
| R5 | `val_geracao` e referencia efetiva nao nulas | nulo -> `motivo=valor_nulo` |
| R6 | referencia efetiva = coalesce(`val_geracaoreferenciafinal`, `val_geracaoreferencia`) (padrao) ou so `val_geracaoreferencia` (`--referencia referencia`) | nao existe opcao "final" (zeraria ENE/CNF) |
| R7 | `val_geracao` < 0 | usa 0 no calculo; flag `geracao_negativa` |
| R8 | qualificado = R1 e R2 e R4 e R5 | `eng_mw = max(ref_ef - ger, 0)`; `eng_mwh = eng_mw x delta t`; `ger >= ref_ef` -> flag `restrito_sem_eng` |
| R9 | `val_geracaolimitada` nao participa do calculo | flags `limite_zero` (limite = 0 com codigo) e `limite_nao_vinculante` (limite > ref_ef) |
| R10 | `val_disponibilidade` nao participa por padrao | flags `disponibilidade_zero`, `ref_maior_que_disp`, `ger_maior_que_disp`; `--excluir-disp-zero` transforma a primeira em `motivo` |
| R11 | lacunas nao sao reindexadas | intervalos presentes vs esperados por usina e mes, resumidos por fonte no relatorio |
| R12 | CSV lido em modo estrito | linhas com numero errado de campos sao contadas em `relatorio_carga.md` (0 na janela) |

Ordem de precedencia do `motivo`: instante_invalido > duplicata > sem_restricao > codigo_desconhecido > valor_nulo > disponibilidade_zero (opcional). Energia gerada (para a taxa de corte) = `max(val_geracao, 0) x delta t`, em todas as linhas, restritas ou nao.

## Metricas e sensibilidade

ENG (energia nao gerada) por registro = `max(ref_ef - max(val_geracao, 0), 0) x delta t` nos registros qualificados. Energia gerada = `max(val_geracao, 0) x delta t` em todos os registros. Taxa de corte = ENG / (ENG + energia gerada). Agregacoes em `src/coff/metricas.py`, figuras em `src/coff/figuras.py`, CSVs em `docs/`.

### Resumo anual

<!-- resumo_anual:inicio -->
| ano | fonte | eng_gwh | energia_gerada_gwh | taxa_corte_pct |
|---|---|---|---|---|
| 2023 | EOL | 3149.64 | 91472.75 | 3.33 |
| 2024 | EOL | 9152.15 | 102673.77 | 8.18 |
| 2024 | UFV | 3184.05 | 21054.22 | 13.14 |
| 2025 | EOL | 25411.36 | 111086.36 | 18.62 |
| 2025 | UFV | 10756.73 | 31719.41 | 25.32 |
| 2026 | EOL | 15911.51 | 67103.11 | 19.17 |
| 2026 | UFV | 7948.1 | 24352.79 | 24.61 |
<!-- resumo_anual:fim -->

### Sensibilidade a referencia efetiva

<!-- sensibilidade:inicio -->
Tabela de sensibilidade (R6): ENG por fonte e categoria com referencia efetiva `coalesce(final, referencia)` versus apenas `referencia`, sobre os registros qualificados de toda a janela.

| fonte | categoria | ENG coalesce (GWh) | ENG referencia (GWh) | dif (GWh) | dif (%) |
|---|---|---|---|---|---|
| EOL | energetica | 26711.9 | 26711.9 | 0.0 | 0.0 |
| EOL | confiabilidade | 21308.5 | 21308.5 | 0.0 | 0.0 |
| EOL | eletrica | 5604.3 | 7116.4 | -1512.2 | -21.25 |
| UFV | energetica | 14993.6 | 14993.6 | 0.0 | 0.0 |
| UFV | confiabilidade | 4807.0 | 4807.0 | 0.0 | 0.0 |
| UFV | eletrica | 2088.3 | 2420.5 | -332.2 | -13.72 |

Ocorrencias de PAR: Nenhuma ocorrencia do codigo PAR na janela.
<!-- sensibilidade:fim -->

### Validacao externa

<!-- validacao:inicio -->
Duas referencias publicadas pelo ONS foram encontradas e comparadas com o resultado do pipeline (referencia `coalesce`, todos os registros qualificados):

1. **RT DGL-ONS 0189/2025 (GT Cortes de Geracao, secao 4.2)**: restricoes por razao energetica em 2024 = **4.330 GWh**. Este repositorio: **4,330 GWh** (diferenca +0 GWh, +0.0 %).
2. **Serie mensal "Geracao Nao Realizada (Apurada), eolica + fotovoltaica, % do potencial de geracao"** (apresentacao do ONS no XXXI Simposio Juridico da ABCE, out/2025; a parte de 2023 coincide com a Fig. 4-3 do RT acima), transcrita em `validacao_ons_serie.csv`. Comparacao em 33 meses (2023-01 a 2025-09): correlacao 0.996, erro absoluto medio 0.37 p.p., vies -0.36 p.p. Tabela completa em `validacao_externa.csv`.

| mes | ENG (MWh) | energia gerada (MWh) | taxa repo (%) | taxa ONS (%) | dif (p.p.) |
|---|---|---|---|---|---|
| 2023-01 | 15254.56 | 6167370.78 | 0.25 | 0.3 | -0.05 |
| 2023-02 | 8502.56 | 6447477.9 | 0.13 | 0.2 | -0.07 |
| 2023-03 | 35958.7 | 6027380.14 | 0.59 | 1.0 | -0.41 |
| 2023-04 | 24912.78 | 4811016.82 | 0.52 | 0.6 | -0.08 |
| 2023-05 | 34870.02 | 6836403.66 | 0.51 | 0.5 | 0.01 |
| 2023-06 | 212007.37 | 8500603.36 | 2.43 | 2.6 | -0.17 |
| 2023-07 | 166114.25 | 9815791.02 | 1.66 | 1.8 | -0.14 |
| 2023-08 | 350460.97 | 8897081.94 | 3.79 | 4.2 | -0.41 |
| 2023-09 | 1275166.9 | 8953052.03 | 12.47 | 12.6 | -0.13 |
| 2023-10 | 474469.14 | 9396638.8 | 4.81 | 5.6 | -0.79 |
| 2023-11 | 312388.11 | 7727282.74 | 3.89 | 4.2 | -0.31 |
| 2023-12 | 239533.75 | 7892648.96 | 2.95 | 3.4 | -0.45 |
| 2024-01 | 34024.73 | 5241470.61 | 0.64 | 0.6 | 0.04 |
| 2024-02 | 167904.13 | 6021299.26 | 2.71 | 3.1 | -0.39 |
| 2024-03 | 108052.99 | 5113080.22 | 2.07 | 2.1 | -0.03 |
| 2024-04 | 154672.17 | 7936527.82 | 1.91 | 1.9 | 0.01 |
| 2024-05 | 559807.47 | 10765940.58 | 4.94 | 5.0 | -0.06 |
| 2024-06 | 1029753.71 | 11343742.41 | 8.32 | 8.6 | -0.28 |
| 2024-07 | 1589477.51 | 12670092.5 | 11.15 | 11.8 | -0.65 |
| 2024-08 | 2206203.61 | 13801597.7 | 13.78 | 14.3 | -0.52 |
| 2024-09 | 2636360.54 | 13716677.07 | 16.12 | 16.5 | -0.38 |
| 2024-10 | 1400573.98 | 13057033.37 | 9.69 | 9.9 | -0.21 |
| 2024-11 | 1166822.77 | 12264719.16 | 8.69 | 8.8 | -0.11 |
| 2024-12 | 1282544.27 | 11795799.87 | 9.81 | 9.8 | 0.01 |
| 2025-01 | 776403.31 | 8331990.33 | 8.52 | 10.1 | -1.58 |
| 2025-02 | 2699273.44 | 9635573.26 | 21.88 | 25.8 | -3.92 |
| 2025-03 | 1564510.57 | 11090650.07 | 12.36 | 12.6 | -0.24 |
| 2025-04 | 1129135.98 | 9923556.78 | 10.22 | 10.3 | -0.08 |
| 2025-05 | 2570209.12 | 12647227.15 | 16.89 | 17.2 | -0.31 |
| 2025-06 | 2494842.22 | 12618277.81 | 16.51 | 16.8 | -0.29 |
| 2025-07 | 3385894.69 | 13220252.3 | 20.39 | 20.4 | -0.01 |
| 2025-08 | 4518090.07 | 13671458.78 | 24.84 | 24.7 | 0.14 |
| 2025-09 | 5070819.81 | 14405660.83 | 26.04 | 26.0 | 0.04 |

Leitura: o ONS publica percentuais apurados (com regras da REN ANEEL 1.030/2022 e reconsistencias) e nao a serie bruta; diferencas de alguns pontos percentuais sao esperadas. Nao foi encontrado um total mensal em GWh publicado pelo ONS por fonte.
<!-- validacao:fim -->

## Cruzamento com a 1a Temporada de Acesso 2026

Fonte externa: ONS, **NT-ONS DPL 0083/2026** (1a Temporada de Acesso 2026, "NT 02"), infografico por UF, extrato de 01/09/2026, transcrito a mao em `temporada_acesso_2026_nt02.csv` (MW; vazio = nao informado no mapa). Legenda: **AD** = atendimento direto; **ADVC** = atendimento direto viavel condicionado; **PC** = processo competitivo; **INAB** = inabilitacao por falta de margem (somente geracao; a carga tem 0 MW inabilitado). Totais oficiais: AD 8.060 MW, ADVC 768 MW, PC 2.940 MW, INAB 9.280 MW. O mapa omite parcelas pequenas de AD e ADVC (soma transcrita de AD = 7.751 MW). INAB e PC batem com o total.

Metrica: `eng_por_uf` calcula ENG por UF e categoria, energia gerada e taxa de corte na janela 2025-01 -> ultimo mes (`eng_por_uf.csv`). `cruzar_temporada` faz a juncao por UF (outer) e calcula `frac_inab = inab / (ad + advc + pc + inab)`. Resultado em `cruzamento_temporada.csv` e nas figuras 6 e 7.

Ressalvas: o dado da Temporada e preliminar e nao contempla desistencias. INAB e so geracao. A ENG e realizada em 2025 e 2026 (MWh) e a Temporada e cadastro de 2026 (MW pretendidos). Sao grandezas diferentes. A comparacao e **geografica, nao causal**.

<!-- temporada:inicio -->
Spearman(taxa de corte, fracao inabilitada) = **0.19** (n = 10 UFs com os dois dados).

| UF | ENG (GWh) | gerada (GWh) | taxa (%) | cadastrado (MW) | INAB (MW) | INAB (%) |
|---|---|---|---|---|---|---|
| RN | 19223.9 | 57509.4 | 25.1 | 953.6 | 798.2 | 83.7 |
| BA | 17203.6 | 74083.5 | 18.8 | 6027.0 | 4659.7 | 77.3 |
| MG | 7894.5 | 22601.6 | 25.9 | 1668.6 | 554.2 | 33.2 |
| PI | 5922.8 | 34344.9 | 14.7 | 1488.4 | 1488.4 | 100.0 |
| CE | 4857.9 | 14729.8 | 24.8 | nan | nan | nan |
| PE | 1823.0 | 7937.3 | 18.7 | 594.3 | 473.6 | 79.7 |
| PB | 1137.6 | 7087.9 | 13.8 | 848.5 | 848.5 | 100.0 |
| SP | 757.0 | 3256.1 | 18.9 | 2250.0 | nan | 0.0 |
| RS | 732.8 | 8671.5 | 7.8 | 1658.8 | nan | 0.0 |
| MA | 315.9 | 2798.8 | 10.1 | nan | nan | nan |
| GO | 100.3 | 356.8 | 21.9 | 140.0 | 140.0 | 100.0 |
| SC | 58.4 | 847.9 | 6.4 | nan | nan | nan |
| MS | 0.0 | 36.3 | 0.0 | 68.0 | nan | 0.0 |
| PA | 0.0 | 0.0 | 0.0 | 36.0 | nan | 0.0 |
| PR | 0.0 | 0.0 | 0.0 | 2378.0 | nan | 0.0 |
| RJ | 0.0 | 0.0 | 0.0 | 517.2 | nan | 0.0 |
| SE | 0.0 | 0.0 | 0.0 | 1300.0 | 300.0 | 23.1 |
| AL | 0.0 | 0.0 | 0.0 | 364.5 | nan | 0.0 |
<!-- temporada:fim -->

## Correlacao por razao da restricao

Pergunta: a fracao inabilitada por falta de margem (Temporada de Acesso 2026, por UF) acompanha a taxa de corte **de rede** (CNF + REL) e nao a taxa **energetica** (ENE)? A hipotese e que a analise de margem e o corte de rede medem o mesmo limite fisico local, enquanto o corte energetico e sistemico.

Taxas por UF (janela 2025-01 -> ultimo mes, mesma base de `eng_por_uf`), todas com o mesmo denominador (ENG total + energia gerada), de modo que `taxa_ene + taxa_rede = taxa_total`: `taxa_total`, `taxa_ene`, `taxa_rede` = (CNF + REL) / potencial, `taxa_cnf`, `taxa_rel`; e `share_rede` = (CNF + REL) / ENG total (composicao). Tabela em `cruzamento_por_razao.csv`.

Estatistica: Spearman entre `frac_inab` e cada metrica, nas UFs com os dois dados. O p-valor e bicaudal e obtido por permutacao (enumeracao exata de todas as permutacoes quando n <= 8; caso contrario 100.000 permutacoes aleatorias com semente fixa), sem aproximacao assintotica. Analise de sensibilidade: a mesma tabela sem GO (140 MW cadastrados, 100 % inabilitados). Resultado em `correlacoes_por_razao.csv` e na figura 8.

Ressalva: n = 10 (9 sem GO). Com esse tamanho de amostra, so correlacoes muito fortes (|rho| acima de ~0,65) atingem p < 0,05; a ausencia de significancia nao e evidencia de ausencia de relacao.

<!-- por_razao:inicio -->
| amostra | métrica | ρ | p | n | método |
|---|---|---|---|---|---|
| todas as UFs com os dois dados | taxa_total | 0.193 | 0.5971 | 10 | 100000 permutacoes |
| todas as UFs com os dois dados | taxa_ene | 0.193 | 0.5953 | 10 | 100000 permutacoes |
| todas as UFs com os dois dados | taxa_rede | 0.242 | 0.4984 | 10 | 100000 permutacoes |
| todas as UFs com os dois dados | share_rede | 0.019 | 0.9727 | 10 | 100000 permutacoes |
| sem GO (140 MW, 100 % inabilitado) | taxa_total | 0.111 | 0.7785 | 9 | 100000 permutacoes |
| sem GO (140 MW, 100 % inabilitado) | taxa_ene | -0.009 | 0.9914 | 9 | 100000 permutacoes |
| sem GO (140 MW, 100 % inabilitado) | taxa_rede | 0.519 | 0.1562 | 9 | 100000 permutacoes |
| sem GO (140 MW, 100 % inabilitado) | share_rede | 0.23 | 0.5511 | 9 | 100000 permutacoes |
<!-- por_razao:fim -->

## Cruzamento por ponto de conexao

Objetivo: levar a comparacao da figura 8 da escala de UF para a escala do barramento (ponto de conexao, PAC), cruzando as descricoes de restricao do ONS com os fatores limitantes da NT-ONS DPL 0083/2026. Etapas: (1) descricoes de restricao; (2) barramentos e fatores limitantes da NT 02; (3) mapa usina -> PAC; (4) cruzamento nominal por barramento.

### Etapa 1 — descricoes de restricao

Fonte: `dsc_restricao` (preenchida desde 2025-09). Normalizacao por regras em `src/coff/descricoes.py`: espacos colapsados; referencias numericas removidas (numero de SGI, MOP, "revisao N", codigos entre parenteses), porque a mesma restricao aparece com dezenas de SGIs diferentes; nenhuma descricao e agrupada a mao. De cada descricao normalizada saem `tipo` (Controle de frequencia / Controle do fluxo / Controle de inequacao / Limitacao da transmissao / Esquema / outro), `elemento` (fluxo, LT, SE, TR ou bipolo citado), `tensao_kv` e `classe` (frequencia, exportacao = limites de intercambio do Nordeste como FNESE, FNS, FNEN; local = LT/SE/TR nomeados; outro). Tabelas: `eng_por_descricao.csv` (por descricao, com categoria e origem principais por ENG) e `eng_cnf_ne_por_elemento.csv` (CNF + REL no Nordeste, por elemento, com `classe` e `classe_efetiva`). A `classe_efetiva` separa `intercâmbio nomeado` (FNESE, FNS+FNESE, FNEN), `corredor de exportação` (elemento nomeado com origem predominante sistemica; na janela sao elementos fora do Nordeste ou na fronteira: Rio Novo do Sul, Itabira, Campos, Pocoes III/Padre Paraiso, Colinas/Ribeiro Goncalves), `local NE` (elemento nomeado com origem local) e `outro`. A coluna `classe` original nao muda.

<!-- descricoes:inicio -->
Descricoes distintas apos normalizacao: 227 (registros qualificados desde 2025-09).

**20 maiores descricoes por ENG**

| descrição | tipo | elemento | classe | categoria | origem | ENG (GWh) | usinas | meses |
|---|---|---|---|---|---|---|---|---|
| Controle de frequência do SIN | Controle de frequência | SIN | frequencia | energetica | sistemica | 26342.8 | 242 | 12 |
| Controle de inequação: CONTROLE DE CARREGAMENTO DA TRANSFORMAÇÃO 500/345 KV DA SE RIO NOVO | Controle de inequação | Transformação 500/345 kV da SE Rio Novo do Sul | local | confiabilidade | sistemica | 3701.6 | 209 | 6 |
| Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NA LT 500 KV AÇU III / JAGUARUANA II – C1( | Limitação da transmissão | LT 500 kV Açu III / Jaguaruana II | local | confiabilidade | local | 3331.0 | 55 | 11 |
| Controle do fluxo: FNESE # Fluxo Nordeste/Sudeste | Controle do fluxo | FNESE | exportacao | eletrica | sistemica | 1522.4 | 203 | 12 |
| Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NAS LTS 500 KV AÇU III / QUIXADÁ – C1(V2), | Limitação da transmissão | LTS 500 kV Açu III / Quixadá | local | confiabilidade | local | 1481.8 | 88 | 12 |
| Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NA LT 500 KV JAGUARUANA II / PACATUBA – C1 | Limitação da transmissão | LT 500 kV Jaguaruana II / Pacatuba | local | confiabilidade | local | 498.8 | 70 | 9 |
| Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV ITABIRA 4 / ITABIRA 5 PARA CO | Controle de inequação | LT 230 kV Itabira 4 / Itabira 5 | local | confiabilidade | sistemica | 482.5 | 202 | 2 |
| Controle de inequação: CONTROLE DE CARREGAMENTO DA TRANSFORMAÇÃO 500/345 KV DA SE RIO NOVO | Controle de inequação | Transformação 500/345 kV da SE Rio Novo do Sul | local | confiabilidade | sistemica | 475.4 | 202 | 1 |
| Controle do fluxo: FNS_FNESE # Somatório de FNS+FNESE | Controle do fluxo | FNS+FNESE | exportacao | confiabilidade | sistemica | 418.1 | 195 | 8 |
| Desligamento das LT 525 kV Povo Novo / Marmeleiro C2 | outro | LT 525 kV Povo Novo / Marmeleiro C2 | outro | eletrica | local | 253.6 | 2 | 1 |
| Controle de inequação: LIMITE DE FJUSC EM FUNÇÃO DA POTÊNCIA TRANSMITIDA PELOS BIPOLOS XIN | Controle de inequação | Bipolos Xingu / Estreito e Xingu / Terminal Rio | local | confiabilidade | sistemica | 193.7 | 17 | 8 |
| Controle de inequação: LIMITE DE FJUSC EM FUNÇÃO DA POTÊNCIA TRANSMITIDA PELOS BIPOLOS XIN | Controle de inequação | Bipolos Xingu / Estreito e Xingu / Terminal Rio | local | eletrica | sistemica | 176.1 | 16 | 9 |
| Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV ITABIRA 4 / ITABIRA 5 PARA CO | Controle de inequação | LT 230 kV Itabira 4 / Itabira 5 | local | confiabilidade | sistemica | 162.8 | 203 | 2 |
| Controle do fluxo: FNEN # Fluxo Nordeste/Norte | Controle do fluxo | FNEN | exportacao | eletrica | sistemica | 143.0 | 125 | 7 |
| Controle de inequação: Perda da LT 345 kV Campos / Rio Novo do Sul C1 | Controle de inequação | LT 345 kV Campos / Rio Novo do Sul C1 | local | eletrica | sistemica | 136.9 | 212 | 2 |
| Controle de inequação | Controle de inequação | nan | outro | eletrica | local | 129.1 | 121 | 8 |
| Controle do fluxo: ON_OC_BP_XINGU<6_GW_FJUSC_FNESE # Redução do Limite FNESE em função do  | Controle do fluxo | FNESE | exportacao | eletrica | sistemica | 118.3 | 55 | 5 |
| Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV IRECÊ / MORRO DO CHAPÉU II –  | Controle de inequação | LT 230 kV Irecê / Morro do Chapéu II | local | confiabilidade | local | 117.9 | 25 | 10 |
| Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV BOM NOME / MILAGRES – C1(L1)  | Controle de inequação | LT 230 kV Bom Nome / Milagres | local | confiabilidade | local | 110.4 | 6 | 7 |
| Controle de inequação: LIMITAÇÃO DO FLUXO BAHIA SUDOESTE - IO-ON.NE.2SO | Limitação da transmissão | Fluxo Bahia Sudoeste | local | confiabilidade | local | 103.9 | 19 | 3 |

**ENG de rede (CNF + REL) no Nordeste por classe de elemento**

| classe efetiva | ENG (GWh) | fração (%) |
|---|---|---|
| intercâmbio nomeado | 2199.0 | 16.5 |
| corredor de exportação | 4821.5 | 36.2 |
| local NE | 6146.5 | 46.1 |
| outro | 156.2 | 1.2 |
<!-- descricoes:fim -->

### Etapa 2 — barramentos e fatores limitantes da NT 02

Fonte: NT-ONS DPL 0083/2026 (PDF publico, baixado para `data/externo/`, gitignored). O texto e extraido com a biblioteca padrao (streams FlateDecode via `zlib`) e as tabelas 4-2 (barramentos candidatos do segmento geracao, MUST 2027–2031), 4-3 (vencedores do LRCAP 2026, marcados `lrcap`) e as tabelas "Capacidade Remanescente e Fatores Limitantes" da secao 6 sao lidas por regex em `src/coff/nt02.py` (`scripts/extrair_nt02.py`). Para cada barramento vale a tabela do ultimo produto disponivel (2031). Resultado derivado: `INAB` se a capacidade remanescente do barramento e 0; `PC` se e positiva e menor que o MUST (limite compartilhado, ex. Alegrete 2 + Livramento 3); `ADVC` se o fator cita uma configuracao condicionante; `AD` caso contrario. `elementos_citados` extrai LT/SE/TR/rede do texto do fator; o fator generico "violacao dos limites de intercambio ou de fluxo previamente definidos" (todos os barramentos inabilitados do Nordeste) vira "limites de intercambio/fluxo (exportacao do Nordeste)". Tabela: `nt02_barramentos_geracao.csv`. Validacao: soma do INAB por UF contra a transcricao do infografico; onde diverge, a NT prevalece: `temporada_acesso_2026_nt02.csv` passa a usar o INAB da NT como referencia (`inab_mw`), guarda o valor transcrito em `inab_mw_infografico` e registra a origem em `fonte`. Unica divergencia encontrada: **BA, 4.659,7 MW na NT contra 4.684,4 MW no infografico (24,7 MW)**; a origem da diferenca nao esta na NT. As figuras 6 a 8 e os CSVs de cruzamento usam o valor da NT.

<!-- nt02:inicio -->
36 barramentos do segmento geracao (10 do LRCAP 2026). Resultado: {'INAB': 21, 'AD': 12, 'PC': 2, 'ADVC': 1}.

| UF | barramento | kV | MUST 2031 | cap. rem. 2031 | resultado | LRCAP | fator limitante |
|---|---|---|---|---|---|---|---|
| GO | Bandeirantes | 230 | 140.0 | 0.0 | INAB |  | Sobrecarga na LT 230 kV C. Dourada - Itumbiara em regime normal de operação. |
| MG | Montes Claros 2 - Irapé C1 | 345 | 300.0 | 0.0 | INAB |  | Colapso de tensão após contingências simples na rede de 500 kV da malha Goiás Minas Gerais São Paulo seguidas  |
| MG | Serra das Almas II | 500 | 254.2 | 0.0 | INAB |  | Colapso de tensão após contingências simples na rede de 500 kV da malha Goiás Minas Gerais São Paulo seguidas  |
| RJ | Lagos | 500 | 17.2 | 17.2 | AD |  | Não foram encontradas violações na região em análise para o valor cadastrado. |
| SP | Getulina | 440 | 300.0 | 300.0 | ADVC |  | Não foram encontradas violações na região em análise para o valor cadastrado. Configuração G descrita na |
| BA | Ourolândia II | 500 | 875.1 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| BA | Correntina | 500 | 500.0 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| BA | Sol do Sertão | 500 | 586.9 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| BA | Gentio do Ouro II | 500 | 784.8 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| BA | Campo Formoso II | 500 | 824.4 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| BA | Campo Formoso II Barra II C1 | 500 | 525.0 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| BA | Brumado II | 230 | 293.5 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| BA | Ibicoara | 230 | 270.0 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| PB | Santa Luzia | 500 | 848.5 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| PE | Luiz Gonzaga | 500 | 473.6 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| PI | Curral Novo do Piauí II | 500 | 769.1 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| PI | Queimada Nova II | 500 | 359.6 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| PI | Parnaíba III | 230 | 255.0 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| PI | São João do Piauí | 230 | 104.7 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| RN | Ceará Mirim II | 500 | 500.0 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| RN | João Câmara III | 230 | 295.8 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| RN | Touros | 230 | 2.5 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| SE | Itabaiana | 230 | 300.0 | 0.0 | INAB |  | Incapacidade de acréscimo de nova geração devido a violação dos limites de intercâmbio ou de fluxo previamente |
| RS | Alegrete 2 | 230 | 185.25 | 100.0 | PC |  | Sobrecarga na LT 230 kV Alegrete 2 Maçambará, na contingência da LT 230 kV Maçambará UTE Uruguaiana, na carga  |
| RS | Livramento 3 | 230 | 807.5 | 360.0 | PC |  | Sobrecarga na LT 230 kV Bagé 2 Livramento 2, em condição normal de operação, na carga máxima noturna de invern |
| RS | Santa Vitória do Palmar 2 | 525 | 616.0 | 616.0 | AD |  | Não foram encontradas violações na região em análise para o valor cadastrado. |
| MG | São Simão | 500 | 308.561 | 308.561 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |
| AL | Rio Largo II | 230 | 364.538 | 364.538 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |
| BA | Camaçari IV | 230 | 18.31 | 18.31 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |
| BA | Polo | 230 | 79.024 | 79.024 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |
| PE | Suape II | 230 | 120.724 | 120.724 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |
| RN | Açu II | 230 | 50.0 | 50.0 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |
| MS | Imbirussú | 230 | 68.0 | 68.0 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |
| PR | Gralha Azul | 230 | 220.0 | 220.0 | AD | sim | Sobrecarga na LT 230 kV Gralha Azul - Umbará, em regime normal de operação, na carga máxima noturna de verão. |
| PR | Areia | 525 | 860.0 | 860.0 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |
| PR | Segredo | 525 | 1266.0 | 1266.0 | AD | sim | Não foram encontradas violações na região em análise para o valor cadastrado. |

**Validacao do INAB por UF (NT x infografico)**

| UF | INAB NT (MW) | INAB infografico (MW) | dif (MW) |
|---|---|---|---|
| BA | 4659.7 | 4684.4 | -24.7 |
| GO | 140.0 | 140.0 | 0.0 |
| MG | 554.2 | 554.2 | 0.0 |
| PB | 848.5 | 848.5 | 0.0 |
| PE | 473.6 | 473.6 | 0.0 |
| PI | 1488.4 | 1488.4 | 0.0 |
| RN | 798.3 | 798.2 | 0.0 |
| SE | 300.0 | 300.0 | 0.0 |

Divergencias: BA: NT 4659.7 MW vs infográfico 4684.4 MW (dif -24.7).
<!-- nt02:fim -->

### Etapa 3 — mapa usina/conjunto -> ponto de conexao

Fontes (portal de dados abertos do ONS, via CKAN): `modalidade-usina` (coluna `nom_pontoconexao`, chave `ceg`) e `usina_conjunto` (relacao conjunto -> usinas, chave `id_ons_conjunto`/`ceg`), baixadas para `data/externo/`. Cadeia: `id_ons` do agregado -> usinas ativas do conjunto -> `ceg` -> ponto de conexao. O nome do ponto e texto livre e e normalizado por regras em `src/coff/pac.py` (sem acentos, maiusculas, tensao extraida, prefixos "SE/SUB" e circuitos removidos, romanos -> arabicos); a lista resultante (`pacs_distintos.csv`) fica para revisao de grafias pelo autor. Conjunto com um PAC que concentra >= 90 % da potencia autorizada -> `metodo=ons_cadastro`, `confianca=alta`; com mais de um PAC real -> uma linha por PAC com `fracao_potencia` (rateio pela potencia autorizada), `metodo=rateio_potencia`, `confianca=media`; usina individual -> juncao direta por `ceg`; sem casamento -> PAC nulo, `metodo=nao_casado`, contado. Tabela: `mapa_usina_pac.csv` (uma linha por id_ons x PAC).

<!-- mapa_pac:inicio -->
Mapa: 303 linhas (id_ons x PAC) para 282 usinas/conjuntos; 12 sem PAC. PACs distintos apos normalizacao: 123 (`pacs_distintos.csv`).

**Cobertura por metodo e confianca** (ENG 2025-01 -> ultimo mes)

| método | confiança | id_ons | ENG (GWh) | ENG (%) |
|---|---|---|---|---|
| nao_casado | — | 12 | 1004.9 | 1.7 |
| ons_cadastro | alta | 250 | 54808.4 | 91.3 |
| rateio_potencia | media | 20 | 4214.4 | 7.0 |

**20 maiores usinas/conjuntos por ENG e seu PAC**

| id_ons | usina/conjunto | UF | fonte | ENG (GWh) | método | confiança | PAC |
|---|---|---|---|---|---|---|---|
| CJU_MGJAN | Conj. Janaúba | MG | UFV | 1668.9 | ons_cadastro | alta | JANAUBA 3 500 kV (100 %) |
| CJU_MGARN | Conj. Arinos 2 500 kV | MG | UFV | 1080.0 | ons_cadastro | alta | ARINOS 2 500 kV (100 %) |
| CJU_RNCAJ1 | Conj. Caju | RN | EOL | 1057.6 | ons_cadastro | alta | ACU 3 500 kV (100 %) |
| CJU_RNRDV | Conj. Rio do Vento | RN | EOL | 1021.2 | ons_cadastro | alta | CEARA MIRIM 2 500 kV (100 %) |
| CJU_MGVST1 | Conj. Vista Alegre - Janaúba | MG | UFV | 937.2 | ons_cadastro | alta | JANAUBA 3 500 kV (100 %) |
| CJU_RNRVE | Conj. Rio do Vento Expansão | RN | EOL | 910.9 | ons_cadastro | alta | CEARA MIRIM 2 500 kV (100 %) |
| CJU_BASAR | Conj. Eolico Serra do Assurua | BA | EOL | 889.1 | ons_cadastro | alta | GENTIO DO OURO 2 230 kV (100 %) |
| CJU_RNSAG | Conj. Santo Agostinho | RN | EOL | 855.6 | ons_cadastro | alta | MONTE VERDE 500 kV (100 %) |
| CJU_BANHZ | Conj. Novo Horizonte | BA | EOL | 799.3 | ons_cadastro | alta | SOL DO SERTAO 500 kV (100 %) |
| CJU_BALRA | Conj. Laranjeiras | BA | EOL | 780.8 | ons_cadastro | alta | GENTIO DO OURO 2 230 kV (100 %) |
| CJU_RNEMVD | Conj. Monte Verde | RN | EOL | 767.2 | rateio_potencia | media | SECC. LT ACU 3 – JOAO CAMARA 3 500 kV (52 %); MONTE VERDE 500 kV (48 %) |
| CJU_RN5ESMA | Conj. Serra do Mel a | RN | EOL | 757.7 | ons_cadastro | alta | ACU 3 500 kV (100 %) |
| CJU_PILDV | Conj. Lagoa dos Ventos | PI | EOL | 757.5 | ons_cadastro | alta | SAO JOAO DO PIAUI 500 kV (100 %) |
| CJU_PI5FGID | Conj. Fotovoltaico Gilbués II 500 kV | PI | UFV | 736.4 | ons_cadastro | alta | GILBUES 2 500 kV (100 %) |
| CJU_PI4ECNP | Conjunto Eólico Curral Novo do Piaui II 230kV | PI | EOL | 734.0 | ons_cadastro | alta | CURRAL NOVO DO PIAUI 2 230 kV (100 %) |
| CJU_RN4EMSD | Conj. Eólico Mossoró II 230kV | RN | EOL | 707.5 | ons_cadastro | alta | MOSSORO 2 230 kV (100 %) |
| CJU_BASSD | Conj. Sol do Sertão | BA | UFV | 701.9 | ons_cadastro | alta | SECC. LT BOM JESUS DA LAPA 2 – GENTIO DO OURO 2 500 kV (100 %) |
| CJU_RNCMR | Conj. Cumaru | RN | EOL | 676.4 | ons_cadastro | alta | JOAO CAMARA 3 230 kV (100 %) |
| CJU_RN5ESMB | Conj. Serra do Mel B | RN | EOL | 664.8 | ons_cadastro | alta | ACU 3 500 kV (100 %) |
| CJU_PIVSR | Conj. São Roque | PI | EOL | 657.7 | ons_cadastro | alta | QUEIMADA NOVA 2 500 kV (100 %) |
<!-- mapa_pac:fim -->

### Etapa 4 — cruzamento nominal por barramento

Sigla da NT 02 -> nome do PAC: `nt02_siglas_pac.csv` (transcrita pelo autor). Adjacencias em `adjacencia_pac.csv`, geradas por regra (`origem=regra`: mesmo PAC; ICG <-> SE homonima; seccionamento de LT/LD <-> as duas SEs do par; Queimada Nova <-> Queimada Nova 2 e Santa Vitoria do Palmar <-> ... 2; a mesma SE em niveis de tensao distintos ja e uma chave so) e revisadas a mao (linhas com outra `origem` sao preservadas nas reexecucoes). Propostas de adjacencia por corredor, extraidas dos elementos "LT X / Y" das descricoes de corte e dos extremos dos seccionamentos, ficam em `adjacencia_propostas.csv` apenas como registro: **as 7 propostas foram rejeitadas pelo autor**. Criterio adotado: a ENG pertence ao PAC do cadastro; relacoes de corredor entram pela condicao B (elemento nomeado nas descricoes de corte), nao por agregacao de usinas de outros PACs. Por barramento: usinas do mapa cujo PAC e o do barramento ou adjacente (ENG ponderada por `fracao_potencia`), ENG 2025-01 -> ultimo mes total e por categoria, taxa de corte, top 3 descricoes (desde 2025-09), fator limitante e resultado. `coincidencia` (regra do autor): no Nordeste, verdadeira quando (A) o barramento e INAB e a ENG de rede (CNF + REL) das usinas adjacentes e majoritariamente das classes efetivas "intercâmbio nomeado" ou "corredor de exportação", ou (B) as descricoes de corte nomeiam um elemento local do mesmo corredor do barramento; fora do Nordeste, (C) quando um elemento citado no fator limitante da NT aparece nas descricoes de corte. A coluna `condicao` registra qual se aplicou. Tabela: `cruzamento_pac.csv`.

<!-- cruzamento_pac:inicio -->
Adjacencias por regra: 35 linhas (`adjacencia_pac.csv`); siglas sem correspondente no mapa: ["ULG = Luiz Gonzaga -> chave 'LUIZ GONZAGA' nao esta no mapa", "PBT = Parnaíba 3 -> chave 'PARNAIBA 3' nao esta no mapa", "CRT = Correntina -> chave 'CORRENTINA' nao esta no mapa", "CAF-II = Campo Formoso 2 -> chave 'CAMPO FORMOSO 2' nao esta no mapa", "ICA = Ibicoara -> chave 'IBICOARA' nao esta no mapa", "ITB = Itabaiana -> chave 'ITABAIANA' nao esta no mapa", "STBD = Bandeirantes -> chave 'BANDEIRANTES' nao esta no mapa", "MCL2_IRAE = Montes Claros 2 -> chave 'MONTES CLAROS 2' nao esta no mapa", "LGO = Lagos -> chave 'LAGOS' nao esta no mapa", "ALE2 = Alegrete 2 -> chave 'ALEGRETE 2' nao esta no mapa"]. Propostas de corredor (nao aplicadas): 7 (`adjacencia_propostas.csv`).

Barramentos com ENG > 0: 17 de 36; com coincidencia = true: 11 de 17.

| sigla | UF | barramento | resultado | usinas | ENG | ENE | CNF | REL | taxa % | rede exp. % | coinc. | condição |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| JCT | RN | João Câmara III | INAB | 17 | 5202 | 2392 | 2704 | 106 | 32.6 | 21.0 | True | B: descrições nomeiam elemento local do corredor (LT 500 kV  |
| GDO | BA | Gentio do Ouro II | INAB | 5 | 3454 | 1885 | 619 | 950 | 19.5 | 96.0 | True | A: INAB e ENG de rede majoritaria em intercâmbio/corredor de |
| OUR | BA | Ourolândia II | INAB | 11 | 2625 | 1707 | 567 | 351 | 13.5 | 70.0 | True | A: INAB e ENG de rede majoritaria em intercâmbio/corredor de |
| CID | RN | Ceará Mirim II | INAB | 2 | 1932 | 927 | 988 | 16 | 23.7 | 25.0 | True | B: descrições nomeiam elemento local do corredor (LT 500 kV  |
| SLD | PB | Santa Luzia | INAB | 8 | 1373 | 1097 | 213 | 63 | 11.2 | 95.0 | True | A: INAB e ENG de rede majoritaria em intercâmbio/corredor de |
| CNP | PI | Curral Novo do Piauí II | INAB | 9 | 1332 | 1004 | 225 | 102 | 10.7 | 74.0 | True | A: INAB e ENG de rede majoritaria em intercâmbio/corredor de |
| SJI | PI | São João do Piauí | INAB | 6 | 1322 | 955 | 256 | 110 | 14.6 | 97.0 | True | A: INAB e ENG de rede majoritaria em intercâmbio/corredor de |
| TRS | RN | Touros | INAB | 4 | 1198 | 658 | 527 | 13 | 31.6 | 33.0 | True | B: descrições nomeiam elemento local do corredor (SE Touros. |
| QND | PI | Queimada Nova II | INAB | 2 | 1120 | 831 | 273 | 16 | 12.7 | 86.0 | True | A: INAB e ENG de rede majoritaria em intercâmbio/corredor de |
| SDS | BA | Sol do Sertão | INAB | 1 | 799 | 365 | 156 | 278 | 27.6 | 96.0 | True | A: INAB e ENG de rede majoritaria em intercâmbio/corredor de |
| ACD | RN | Açu II | AD | 5 | 667 | 330 | 321 | 17 | 34.9 | 30.0 | False |  |
| SPA2 | RS | Santa Vitória do Palmar 2 | AD | 1 | 298 | 124 | 0 | 175 | 11.0 | 0.0 | False |  |
| BDD | BA | Brumado II | INAB | 1 | 137 | 68 | 28 | 41 | 23.6 | 98.0 | True | A: INAB e ENG de rede majoritaria em intercâmbio/corredor de |
| MCL2_IRAE | MG | Montes Claros 2 - Irapé C1 | INAB | 1 | 88 | 63 | 16 | 9 | 25.0 | 67.0 | False |  |
| GET | SP | Getulina | ADVC | 1 | 86 | 85 | 0 | 1 | 19.6 | 9.0 | False |  |
| LIV3 | RS | Livramento 3 | PC | 1 | 62 | 62 | 0 | 0 | 4.8 | 100.0 | False |  |
| SDA2 | MG | Serra das Almas II | INAB | 1 | 44 | 37 | 2 | 4 | 5.2 | 79.0 | False |  |
| PLO | BA | Polo | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| CMQ | BA | Camaçari IV | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| IMB | MS | Imbirussú | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| GRL | PR | Gralha Azul | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| ARE | PR | Areia | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| RLD | AL | Rio Largo II | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| SSSE | MG | São Simão | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| SUD | PE | Suape II | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| STBD | GO | Bandeirantes | INAB | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| ALE2 | RS | Alegrete 2 | PC | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| ITB | SE | Itabaiana | INAB | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| PBT | PI | Parnaíba III | INAB | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| ULG | PE | Luiz Gonzaga | INAB | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| ICA | BA | Ibicoara | INAB | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| CAF-II BRR-II | BA | Campo Formoso II Barra II C1 | INAB | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| CAF-II | BA | Campo Formoso II | INAB | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| CRT | BA | Correntina | INAB | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| LGO | RJ | Lagos | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
| SGD | PR | Segredo | AD | 0 | 0 | 0 | 0 | 0 | nan | nan | False |  |
<!-- cruzamento_pac:fim -->

## Limitacoes

- Os dados publicados pelo ONS fazem parte de um processo de consistencia recorrente e podem ser atualizados apos a publicacao. O cache local so e refeito com `--forcar`.
- A coluna `dsc_restricao` (descricao textual da restricao) **so existe a partir de 2025_01** (EOL 2023_01→2024_12 e UFV 2024_04→2024_12 nao a possuem; 33 arquivos, criada nula) e **so e preenchida pelo ONS a partir de 2025_09**. De 2025_01 a 2025_08 a coluna existe e esta vazia em todas as linhas. Por isso a metrica "top descricoes" (figura 5, `top_descricoes.csv`) cobre 2025_09 em diante. A ENG dos registros restritos de 2025_01 a 2025_08 aparece como "(sem descricao)" na tabela e fica fora da figura 5.
- O codigo de razao **PAR** ("restricao indicada no parecer de acesso") consta do dicionario de dados e **nao ocorre em nenhum dos 73 meses x fonte** da janela (contagem mes a mes em `relatorio_carga.md`). E tratado como codigo conhecido e contado. A categoria "parecer de acesso" aparece vazia.
- Os conjuntos de usinas nao sao desagregados por usina individual (datasets `*_detail` fora do escopo).
- Na eolica, usinas e conjuntos entram e saem do dataset ao longo da janela (153 a 164 por mes). A serie por usina nao e um painel balanceado.
- A apuracao regulatoria (REN ANEEL 1.030/2022) nao e reproduzida. Nao ha franquias nem regras de elegibilidade por usina. A ENG aqui e uma medida descritiva.
