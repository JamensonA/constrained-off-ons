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
| BA | 17203.6 | 74083.5 | 18.8 | 6051.7 | 4684.4 | 77.4 |
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

|
 
d
e
s
c
r
i
ç
ã
o
 
|
 
t
i
p
o
 
|
 
e
l
e
m
e
n
t
o
 
|
 
c
l
a
s
s
e
 
|
 
c
a
t
e
g
o
r
i
a
 
|
 
o
r
i
g
e
m
 
|
 
E
N
G
 
(
G
W
h
)
 
|
 
u
s
i
n
a
s
 
|
 
m
e
s
e
s
 
|


|
-
-
-
|
-
-
-
|
-
-
-
|
-
-
-
|
-
-
-
|
-
-
-
|
-
-
-
|
-
-
-
|
-
-
-
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
f
r
e
q
u
ê
n
c
i
a
 
d
o
 
S
I
N
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
f
r
e
q
u
ê
n
c
i
a
 
|
 
S
I
N
 
|
 
f
r
e
q
u
e
n
c
i
a
 
|
 
e
n
e
r
g
e
t
i
c
a
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
2
6
3
4
2
.
8
 
|
 
2
4
2
 
|
 
1
2
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
C
O
N
T
R
O
L
E
 
D
E
 
C
A
R
R
E
G
A
M
E
N
T
O
 
D
A
 
T
R
A
N
S
F
O
R
M
A
Ç
Ã
O
 
5
0
0
/
3
4
5
 
K
V
 
D
A
 
S
E
 
R
I
O
 
N
O
V
O
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
T
r
a
n
s
f
o
r
m
a
ç
ã
o
 
5
0
0
/
3
4
5
 
k
V
 
d
a
 
S
E
 
R
i
o
 
N
o
v
o
 
d
o
 
S
u
l
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
3
7
0
1
.
6
 
|
 
2
0
9
 
|
 
6
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
L
I
M
I
T
A
Ç
Ã
O
 
D
A
 
T
R
A
N
S
M
I
S
S
Ã
O
 
N
A
 
L
T
 
5
0
0
 
K
V
 
A
Ç
U
 
I
I
I
 
/
 
J
A
G
U
A
R
U
A
N
A
 
I
I
 
–
 
C
1
(
 
|
 
L
i
m
i
t
a
ç
ã
o
 
d
a
 
t
r
a
n
s
m
i
s
s
ã
o
 
|
 
L
T
 
5
0
0
 
k
V
 
A
ç
u
 
I
I
I
 
/
 
J
a
g
u
a
r
u
a
n
a
 
I
I
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
l
o
c
a
l
 
|
 
3
3
3
1
.
0
 
|
 
5
5
 
|
 
1
1
 
|


|
 
C
o
n
t
r
o
l
e
 
d
o
 
f
l
u
x
o
:
 
F
N
E
S
E
 
#
 
F
l
u
x
o
 
N
o
r
d
e
s
t
e
/
S
u
d
e
s
t
e
 
|
 
C
o
n
t
r
o
l
e
 
d
o
 
f
l
u
x
o
 
|
 
F
N
E
S
E
 
|
 
e
x
p
o
r
t
a
c
a
o
 
|
 
e
l
e
t
r
i
c
a
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
1
5
2
2
.
4
 
|
 
2
0
3
 
|
 
1
2
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
L
I
M
I
T
A
Ç
Ã
O
 
D
A
 
T
R
A
N
S
M
I
S
S
Ã
O
 
N
A
S
 
L
T
S
 
5
0
0
 
K
V
 
A
Ç
U
 
I
I
I
 
/
 
Q
U
I
X
A
D
Á
 
–
 
C
1
(
V
2
)
,
 
|
 
L
i
m
i
t
a
ç
ã
o
 
d
a
 
t
r
a
n
s
m
i
s
s
ã
o
 
|
 
L
T
S
 
5
0
0
 
k
V
 
A
ç
u
 
I
I
I
 
/
 
Q
u
i
x
a
d
á
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
l
o
c
a
l
 
|
 
1
4
8
1
.
8
 
|
 
8
8
 
|
 
1
2
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
L
I
M
I
T
A
Ç
Ã
O
 
D
A
 
T
R
A
N
S
M
I
S
S
Ã
O
 
N
A
 
L
T
 
5
0
0
 
K
V
 
J
A
G
U
A
R
U
A
N
A
 
I
I
 
/
 
P
A
C
A
T
U
B
A
 
–
 
C
1
 
|
 
L
i
m
i
t
a
ç
ã
o
 
d
a
 
t
r
a
n
s
m
i
s
s
ã
o
 
|
 
L
T
 
5
0
0
 
k
V
 
J
a
g
u
a
r
u
a
n
a
 
I
I
 
/
 
P
a
c
a
t
u
b
a
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
l
o
c
a
l
 
|
 
4
9
8
.
8
 
|
 
7
0
 
|
 
9
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
C
O
N
T
R
O
L
E
 
D
E
 
C
A
R
R
E
G
A
M
E
N
T
O
 
D
A
 
L
T
 
2
3
0
 
K
V
 
I
T
A
B
I
R
A
 
4
 
/
 
I
T
A
B
I
R
A
 
5
 
P
A
R
A
 
C
O
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
L
T
 
2
3
0
 
k
V
 
I
t
a
b
i
r
a
 
4
 
/
 
I
t
a
b
i
r
a
 
5
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
4
8
2
.
5
 
|
 
2
0
2
 
|
 
2
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
C
O
N
T
R
O
L
E
 
D
E
 
C
A
R
R
E
G
A
M
E
N
T
O
 
D
A
 
T
R
A
N
S
F
O
R
M
A
Ç
Ã
O
 
5
0
0
/
3
4
5
 
K
V
 
D
A
 
S
E
 
R
I
O
 
N
O
V
O
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
T
r
a
n
s
f
o
r
m
a
ç
ã
o
 
5
0
0
/
3
4
5
 
k
V
 
d
a
 
S
E
 
R
i
o
 
N
o
v
o
 
d
o
 
S
u
l
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
4
7
5
.
4
 
|
 
2
0
2
 
|
 
1
 
|


|
 
C
o
n
t
r
o
l
e
 
d
o
 
f
l
u
x
o
:
 
F
N
S
_
F
N
E
S
E
 
#
 
S
o
m
a
t
ó
r
i
o
 
d
e
 
F
N
S
+
F
N
E
S
E
 
|
 
C
o
n
t
r
o
l
e
 
d
o
 
f
l
u
x
o
 
|
 
F
N
S
+
F
N
E
S
E
 
|
 
e
x
p
o
r
t
a
c
a
o
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
4
1
8
.
1
 
|
 
1
9
5
 
|
 
8
 
|


|
 
D
e
s
l
i
g
a
m
e
n
t
o
 
d
a
s
 
L
T
 
5
2
5
 
k
V
 
P
o
v
o
 
N
o
v
o
 
/
 
M
a
r
m
e
l
e
i
r
o
 
C
2
 
|
 
o
u
t
r
o
 
|
 
L
T
 
5
2
5
 
k
V
 
P
o
v
o
 
N
o
v
o
 
/
 
M
a
r
m
e
l
e
i
r
o
 
C
2
 
|
 
o
u
t
r
o
 
|
 
e
l
e
t
r
i
c
a
 
|
 
l
o
c
a
l
 
|
 
2
5
3
.
6
 
|
 
2
 
|
 
1
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
L
I
M
I
T
E
 
D
E
 
F
J
U
S
C
 
E
M
 
F
U
N
Ç
Ã
O
 
D
A
 
P
O
T
Ê
N
C
I
A
 
T
R
A
N
S
M
I
T
I
D
A
 
P
E
L
O
S
 
B
I
P
O
L
O
S
 
X
I
N
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
B
i
p
o
l
o
s
 
X
i
n
g
u
 
/
 
E
s
t
r
e
i
t
o
 
e
 
X
i
n
g
u
 
/
 
T
e
r
m
i
n
a
l
 
R
i
o
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
1
9
3
.
7
 
|
 
1
7
 
|
 
8
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
L
I
M
I
T
E
 
D
E
 
F
J
U
S
C
 
E
M
 
F
U
N
Ç
Ã
O
 
D
A
 
P
O
T
Ê
N
C
I
A
 
T
R
A
N
S
M
I
T
I
D
A
 
P
E
L
O
S
 
B
I
P
O
L
O
S
 
X
I
N
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
B
i
p
o
l
o
s
 
X
i
n
g
u
 
/
 
E
s
t
r
e
i
t
o
 
e
 
X
i
n
g
u
 
/
 
T
e
r
m
i
n
a
l
 
R
i
o
 
|
 
l
o
c
a
l
 
|
 
e
l
e
t
r
i
c
a
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
1
7
6
.
1
 
|
 
1
6
 
|
 
9
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
C
O
N
T
R
O
L
E
 
D
E
 
C
A
R
R
E
G
A
M
E
N
T
O
 
D
A
 
L
T
 
2
3
0
 
K
V
 
I
T
A
B
I
R
A
 
4
 
/
 
I
T
A
B
I
R
A
 
5
 
P
A
R
A
 
C
O
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
L
T
 
2
3
0
 
k
V
 
I
t
a
b
i
r
a
 
4
 
/
 
I
t
a
b
i
r
a
 
5
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
1
6
2
.
8
 
|
 
2
0
3
 
|
 
2
 
|


|
 
C
o
n
t
r
o
l
e
 
d
o
 
f
l
u
x
o
:
 
F
N
E
N
 
#
 
F
l
u
x
o
 
N
o
r
d
e
s
t
e
/
N
o
r
t
e
 
|
 
C
o
n
t
r
o
l
e
 
d
o
 
f
l
u
x
o
 
|
 
F
N
E
N
 
|
 
e
x
p
o
r
t
a
c
a
o
 
|
 
e
l
e
t
r
i
c
a
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
1
4
3
.
0
 
|
 
1
2
5
 
|
 
7
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
P
e
r
d
a
 
d
a
 
L
T
 
3
4
5
 
k
V
 
C
a
m
p
o
s
 
/
 
R
i
o
 
N
o
v
o
 
d
o
 
S
u
l
 
C
1
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
L
T
 
3
4
5
 
k
V
 
C
a
m
p
o
s
 
/
 
R
i
o
 
N
o
v
o
 
d
o
 
S
u
l
 
C
1
 
|
 
l
o
c
a
l
 
|
 
e
l
e
t
r
i
c
a
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
1
3
6
.
9
 
|
 
2
1
2
 
|
 
2
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
n
a
n
 
|
 
o
u
t
r
o
 
|
 
e
l
e
t
r
i
c
a
 
|
 
l
o
c
a
l
 
|
 
1
2
9
.
1
 
|
 
1
2
1
 
|
 
8
 
|


|
 
C
o
n
t
r
o
l
e
 
d
o
 
f
l
u
x
o
:
 
O
N
_
O
C
_
B
P
_
X
I
N
G
U
<
6
_
G
W
_
F
J
U
S
C
_
F
N
E
S
E
 
#
 
R
e
d
u
ç
ã
o
 
d
o
 
L
i
m
i
t
e
 
F
N
E
S
E
 
e
m
 
f
u
n
ç
ã
o
 
d
o
 
 
|
 
C
o
n
t
r
o
l
e
 
d
o
 
f
l
u
x
o
 
|
 
F
N
E
S
E
 
|
 
e
x
p
o
r
t
a
c
a
o
 
|
 
e
l
e
t
r
i
c
a
 
|
 
s
i
s
t
e
m
i
c
a
 
|
 
1
1
8
.
3
 
|
 
5
5
 
|
 
5
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
C
O
N
T
R
O
L
E
 
D
E
 
C
A
R
R
E
G
A
M
E
N
T
O
 
D
A
 
L
T
 
2
3
0
 
K
V
 
I
R
E
C
Ê
 
/
 
M
O
R
R
O
 
D
O
 
C
H
A
P
É
U
 
I
I
 
–
 
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
L
T
 
2
3
0
 
k
V
 
I
r
e
c
ê
 
/
 
M
o
r
r
o
 
d
o
 
C
h
a
p
é
u
 
I
I
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
l
o
c
a
l
 
|
 
1
1
7
.
9
 
|
 
2
5
 
|
 
1
0
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
C
O
N
T
R
O
L
E
 
D
E
 
C
A
R
R
E
G
A
M
E
N
T
O
 
D
A
 
L
T
 
2
3
0
 
K
V
 
B
O
M
 
N
O
M
E
 
/
 
M
I
L
A
G
R
E
S
 
–
 
C
1
(
L
1
)
 
 
|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
 
|
 
L
T
 
2
3
0
 
k
V
 
B
o
m
 
N
o
m
e
 
/
 
M
i
l
a
g
r
e
s
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
l
o
c
a
l
 
|
 
1
1
0
.
4
 
|
 
6
 
|
 
7
 
|


|
 
C
o
n
t
r
o
l
e
 
d
e
 
i
n
e
q
u
a
ç
ã
o
:
 
L
I
M
I
T
A
Ç
Ã
O
 
D
O
 
F
L
U
X
O
 
B
A
H
I
A
 
S
U
D
O
E
S
T
E
 
-
 
I
O
-
O
N
.
N
E
.
2
S
O
 
|
 
L
i
m
i
t
a
ç
ã
o
 
d
a
 
t
r
a
n
s
m
i
s
s
ã
o
 
|
 
F
l
u
x
o
 
B
a
h
i
a
 
S
u
d
o
e
s
t
e
 
|
 
l
o
c
a
l
 
|
 
c
o
n
f
i
a
b
i
l
i
d
a
d
e
 
|
 
l
o
c
a
l
 
|
 
1
0
3
.
9
 
|
 
1
9
 
|
 
3
 
|

**ENG de rede (CNF + REL) no Nordeste por classe de elemento**

|
 
c
l
a
s
s
e
 
e
f
e
t
i
v
a
 
|
 
E
N
G
 
(
G
W
h
)
 
|
 
f
r
a
ç
ã
o
 
(
%
)
 
|


|
-
-
-
|
-
-
-
|
-
-
-
|


|
 
i
n
t
e
r
c
â
m
b
i
o
 
n
o
m
e
a
d
o
 
|
 
2
1
9
9
.
0
 
|
 
1
6
.
5
 
|


|
 
c
o
r
r
e
d
o
r
 
d
e
 
e
x
p
o
r
t
a
ç
ã
o
 
|
 
4
8
2
1
.
5
 
|
 
3
6
.
2
 
|


|
 
l
o
c
a
l
 
N
E
 
|
 
6
1
4
6
.
5
 
|
 
4
6
.
1
 
|


|
 
o
u
t
r
o
 
|
 
1
5
6
.
2
 
|
 
1
.
2
 
|
<!-- descricoes:fim -->

## Limitacoes

- Os dados publicados pelo ONS fazem parte de um processo de consistencia recorrente e podem ser atualizados apos a publicacao. O cache local so e refeito com `--forcar`.
- A coluna `dsc_restricao` (descricao textual da restricao) **so existe a partir de 2025_01** (EOL 2023_01→2024_12 e UFV 2024_04→2024_12 nao a possuem; 33 arquivos, criada nula) e **so e preenchida pelo ONS a partir de 2025_09**. De 2025_01 a 2025_08 a coluna existe e esta vazia em todas as linhas. Por isso a metrica "top descricoes" (figura 5, `top_descricoes.csv`) cobre 2025_09 em diante. A ENG dos registros restritos de 2025_01 a 2025_08 aparece como "(sem descricao)" na tabela e fica fora da figura 5.
- O codigo de razao **PAR** ("restricao indicada no parecer de acesso") consta do dicionario de dados e **nao ocorre em nenhum dos 73 meses x fonte** da janela (contagem mes a mes em `relatorio_carga.md`). E tratado como codigo conhecido e contado. A categoria "parecer de acesso" aparece vazia.
- Os conjuntos de usinas nao sao desagregados por usina individual (datasets `*_detail` fora do escopo).
- Na eolica, usinas e conjuntos entram e saem do dataset ao longo da janela (153 a 164 por mes). A serie por usina nao e um painel balanceado.
- A apuracao regulatoria (REN ANEEL 1.030/2022) nao e reproduzida. Nao ha franquias nem regras de elegibilidade por usina. A ENG aqui e uma medida descritiva.
