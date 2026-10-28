# Projeto ANP: concentração de mercado de postos de combustíveis por município

Trabalho de **Banco de Dados 2** (IFPB, Prof. Gildo Ferrúcio) sobre dados semiestruturados e bancos de dados distribuídos.
Entrega: 31/10/2026.

**Equipe:** Anderson (dados) e Naira (banco e aplicação).

---

## 1. A base de dados

| | |
|---|---|
| **Nome** | Dados cadastrais dos revendedores varejistas de combustíveis automotivos (postos de combustíveis) |
| **Fonte** | ANP (Agência Nacional do Petróleo, Gás Natural e Biocombustíveis), publicada no portal dados.gov.br |
| **Arquivo** | `dados-cadastrais-revendedores-varejistas-combustiveis-automoveis.csv` |
| **Formato** | CSV, UTF-8, separador `;` |
| **Tamanho** | 45.773 registros e 13 colunas |
| **Período das autorizações** | de 18/08/2000 a 13/10/2026 |
| **Abrangência** | 27 UFs, 5.525 municípios, 38.728 empresas (raízes de CNPJ distintas) e 64 bandeiras |

Cada linha é um posto (CNPJ único). A base é um **cadastro**: não tem vendas, volumes nem preços.

## 2. Problema que a aplicação resolve

O sistema mostra a **concentração de mercado do varejo de combustíveis por município**: quantos postos há por bandeira e por rede (empresa dona, identificada pela raiz do CNPJ), a participação de cada uma e o **HHI** (Índice Herfindahl-Hirschman). Também há uma aba de **qualidade dos dados**, com os postos de cadastro inconsistente.

> **Limitação:** como a base não tem vendas, a concentração é medida pelo **número de postos** (presença), e não pela fatia real de mercado.

A aplicação (Streamlit, `src/app.py`) lê os dados **direto do banco PostgreSQL** e tem quatro abas:

- **Município:** escolhendo UF e município, mostra o total de postos, o número de redes, o HHI por rede e por bandeira, os gráficos e tabelas de postos por bandeira e por rede.
- **Rankings:** municípios mais e menos concentrados (com mínimo de postos ajustável), maiores redes do país e municípios só com bandeira branca.
- **Qualidade dos dados:** postos com cadastro inconsistente, resumo por motivo, filtro e download em CSV.
- **Sobre:** descrição da base, do tratamento e da limitação.

---

## 3. Identificação do esquema original

A base original é uma tabela única e achatada, com 13 colunas, todas lidas como texto.

| Coluna | Significado | % de nulos | Valores distintos | Exemplo |
|---|---|---|---|---|
| `CODIGOISIMP` | Código de identificação do posto na ANP | 0,00 | 45.773 | `1038690` |
| `AUTORIZACAO` | Número da autorização de funcionamento (o prefixo indica o tipo: `PR`, `PF`, `AV`, `PM`, `GNV`) | 0,00 | 45.704 | `PR/AC0167611` |
| `DATAPUBLICACAO` | Data de publicação da autorização | 0,00 | 2.851 | `26/07/2005` |
| `RAZAOSOCIAL` | Razão social da empresa | 0,00 | 36.977 | `AUTO POSTO CAMILA LTDA` |
| `CNPJ` | CNPJ do estabelecimento (14 dígitos) | 0,00 | 45.773 | `05938540000134` |
| `ENDERECO` | Logradouro e número no mesmo campo (`LOGRADOURO,  NÚMERO`) | 0,00 | 42.887 | `AVENIDA JOSE RUI LINO,  500` |
| `COMPLEMENTO` | Complemento do endereço | **70,87** | 8.460 | `KM 26` |
| `BAIRRO` | Bairro | 0,26 | 13.633 | `RAIMUNDO CHAAR` |
| `CEP` | CEP (8 dígitos) | 0,00 | 22.930 | `69932000` |
| `UF` | Unidade da federação | 0,00 | 27 | `AC` |
| `MUNICIPIO` | Município | 0,00 | 5.253 | `BRASILEIA` |
| `BANDEIRA` | Marca do posto (`BANDEIRA BRANCA` = sem marca) | 0,00 | 64 | `VIBRA` |
| `DATAVINCULACAO` | Data de vinculação do posto à bandeira | 0,00 | 5.261 | `26/07/2005` |

Os significados foram deduzidos pelos nomes das colunas e pelos valores. Conferir com o dicionário de dados da página do conjunto no dados.gov.br.

**Características do esquema original que justificam o tratamento:**

- Endereço em um único campo de texto, sem separar tipo, logradouro, número e KM.
- Município, bairro e UF repetidos em cada linha (redundância).
- Empresa (razão social e CNPJ) misturada com o estabelecimento: a mesma empresa aparece em vários postos.
- Datas armazenadas como texto no formato `dd/mm/aaaa`.

---

## 4. Tratamento de dados não conformes

Script `src/perfil.py` (encontra os problemas, exemplos em `exemplos/`) e `src/clean.py` (corrige e marca em `flag_inconsistente`).

| Problema | Quantidade | Exemplo | Tratamento |
|---|---|---|---|
| `COMPLEMENTO` nulo | 32.439 (70,87%) | `KM 26` quando existe | Mantido nulo |
| `BAIRRO` nulo | 124 | `RODOVIA BR 040,  S N` (Ressaquinha, MG) | Mantido nulo e marcado como `bairro_ausente`; no banco, `bairro_id` aceita nulo |
| CEP com 7 dígitos (perdeu o zero à esquerda) | 2.703 (2.698 em SP) | `7401790` (Arujá, SP) | Corrigido para `07401790` (`zfill(8)`) |
| CEP inválido | 4 | `0` (Sorocaba, SP); `15495` (Riolândia, SP) | Convertido em nulo e marcado como `cep_invalido` |
| Datas ausentes | 1 posto | `AUTO POSTO SHOPPING LTDA` (publicação e vinculação vazias) | Marcado como `data_publicacao_ausente` e `data_vinculacao_ausente` |
| `AUTORIZACAO` repetida em CNPJs diferentes | 130 postos (62 números) | `AV/PR178045` em Maringá e em Curitiba | Marcado como `autorizacao_repetida`; **não** usada como chave única |
| `AUTORIZACAO` fora do padrão `XX/UF0000000` | 15 | `MS0025824` (sem o prefixo de tipo) | Marcado como `autorizacao_fora_do_padrao` |
| Espaços duplos ou sobrando em `RAZAOSOCIAL` | 303 | `'AUTO  POSTO FALCÃO LTDA'` | Espaços normalizados |
| Bandeiras com grafia estranha | 944 postos | `ATEM' S` (468), `SABBÁ` (338), ``D`MAIS`` (4) | Tratadas pelo dicionário de sinônimos (seção 6) |
| `COMPLEMENTO` com valor sem significado (`0`) | 225 | `0` | **Não tratado** (ver limitações) |

Resultado do `clean.py`: **273 postos** com alguma inconsistência (`flag_inconsistente = True`). Um mesmo posto pode ter mais de um motivo, e os motivos ficam na coluna `motivo_inconsistencia`.

| Motivo | Postos |
|---|---|
| `autorizacao_repetida` | 130 |
| `bairro_ausente` | 124 |
| `autorizacao_fora_do_padrao` | 15 |
| `cep_invalido` | 4 |
| `data_publicacao_ausente` | 1 |
| `data_vinculacao_ausente` | 1 |

**Dados que estavam corretos:** os 45.773 CNPJs têm 14 dígitos, **dígito verificador válido** e nenhum se repete. As UFs também são todas válidas.

**Exemplo antes e depois (CEP):**

| Posto | CEP antes | CEP depois |
|---|---|---|
| Posto de Serviços Ibirapitanga Ltda (Arujá, SP) | `7401790` | `07401790` |
| Mari Manos Auto Posto Ltda. (Cotia, SP) | `6711250` | `06711250` |
| Petroef Serviços Automotivos Ltda. (Embu das Artes, SP) | `6803000` | `06803000` |

Arquivos de exemplo completos: `exemplos/bairro_nulo.csv`, `cep_7_digitos.csv`, `cep_invalido.csv`, `data_invalida.csv`, `autorizacao_repetida.csv`, `razao_social_espacos.csv`, `bandeira_estranha.csv`, `antes_depois_cep.csv` e `antes_depois_razao_social.csv`.

---

## 5. Padronização de dados: endereço em colunas

Script `src/standardize.py`. O campo `ENDERECO` (`LOGRADOURO,  NÚMERO`) foi separado em **`tipo_logradouro`, `logradouro`, `numero`, `sem_numero` e `km`**.

| Endereço original | tipo | logradouro | número | sem número | km |
|---|---|---|---|---|---|
| `AV. MARECHAL DEODORO,  1700` | AVENIDA | MARECHAL DEODORO | 1700 | não | |
| `RUA ITAJAI,  327-A` | RUA | ITAJAI | 327A | não | |
| `AVENIDA JOÃO PONCE ARRUDA,  S/Nº` | AVENIDA | JOÃO PONCE ARRUDA | | sim | |
| `RODOVIA BR 116 - KM 119,  S/N` | RODOVIA | BR 116 | | sim | 119 |
| `RODOVIA BR ZERO VINTE KM 76,  S/N` | RODOVIA | BR 020 | | sim | 76 |
| `RODOVIA RODOVIA BR 101 / BR 418,  S/N` | RODOVIA | BR 101 / BR 418 | | sim | |

Regras aplicadas (quantidade de postos afetados):

| Regra | Postos |
|---|---|
| Tipo abreviado padronizado (`AV.` para `AVENIDA`, `R.` para `RUA`, `ROD.` para `RODOVIA`) | 766 |
| Tipo duplicado removido (`RODOVIA RODOVIA`, `RUA RUA`) | 421 |
| Número com sufixo unificado (`327-A`, `327 A` e `327A` viram `327A`) | 217 |
| KM extraído do endereço | 2.195 |
| KM extraído do complemento | 4.182 |
| Formato de rodovia unificado (`BR-101`, `BR101` e `BR. 101` viram `BR 101`) | 497 |

Resultado: 11.461 postos sem número (rodovias e endereços `S/N`), 6.377 com KM e tipos de logradouro mais comuns `AVENIDA` (19.177), `RUA` (14.484) e `RODOVIA` (7.770).

Exemplos antes e depois: `exemplos/antes_depois_endereco.csv` (15 casos de cada regra).

---

## 6. Sinônimos com completude distinta de informação

Equivalente ao exemplo "cefaleia" e "dor de cabeça" visto em aula: formas diferentes (e com níveis diferentes de detalhe) para o mesmo significado.

**6.1 "Sem número" (Anderson, `standardize.py`).** Sete grafias para a mesma informação, todas convertidas para `sem_numero = True`:

| Grafia original | Postos |
|---|---|
| `S/N` | 7.066 |
| `SN` | 3.971 |
| `S/Nº` | 96 |
| `S N` | 66 |
| `S/N.` | 17 |
| `SNR` | 11 |
| `S/N°` | 8 |

Arquivo completo: `exemplos/sinonimos_sem_numero.csv`.

**6.2 Rodovias (Anderson).** A mesma rodovia escrita de formas diferentes, inclusive **por extenso**:

| Escrita original | Padronizado |
|---|---|
| `BR ZERO QUARENTA` | `BR 040` |
| `BR-CENTO E UM` | `BR 101` |
| `BR TREZENTOS E CINQUENTA E SEIS` | `BR 356` |
| `BR-101`, `BR101`, `BR. 101` | `BR 101` |
| `RODOVIA RODOVIA BR 343` | `RODOVIA` + `BR 343` |

19 postos usavam o número por extenso e 497 tinham formatos diferentes do mesmo número.

**6.3 Bandeiras.** O dicionário `data/bandeiras.csv` tem 12 sinônimos, carregados na tabela `bandeira_sinonimo`. A coluna `posto.bandeira_original` guarda o nome como veio da ANP. As 64 bandeiras originais viram 63.

| Original | Padronizado | Tipo de variação |
|---|---|---|
| `ATEM' S` | `ATEM'S` | grafia (espaço indevido) |
| ``D`MAIS`` | `D'MAIS` | grafia (acento grave no lugar do apóstrofo) |
| `SABBÁ` | `SABBA` | acento |
| `ATLÂNTICA` | `ATLANTICA` | acento |
| `PETROX DISTRIBUIDORA` | `PETROX` | nome mais completo (sufixo) |
| `SETTA DISTRIBUIDORA` | `SETTA` | nome mais completo (sufixo) |
| `TDC DISTRIBUIDORA` | `TDC` | nome mais completo (sufixo) |
| `J.R DISTRIBUIDORA` | `J.R` | nome mais completo (sufixo) |
| `RZD DISTRIBUIDORA` | `RZD` | nome mais completo (sufixo) |
| `SIM DISTRIBUIDOR` | `SIM` | nome mais completo (sufixo) |
| `MASUT DISTRIBUIDORA` | `MASUT` | nome mais completo (sufixo) |
| `RAIZEN MIME` | `RAIZEN` | marca com informação a mais |

Decisões:

- **`RAIZEN MIME`** (206 postos, 205 em Santa Catarina, 61 deles da rede `POSTO MIME S.A.`): unificada a `RAIZEN`, pois o nome contém a bandeira. É uma interpretação, e a unificação aumenta a participação da Raízen em Santa Catarina.
- **`BANDEIRA BRANCA`** (22.050 postos) significa "sem marca" e **não** é sinônimo de nenhuma bandeira.
- **`SP`** (314 postos, 169 no CE, 54 no MA, 37 no PI e 13 em MG, com razões sociais de pequenas empresas e pessoas físicas): não foi possível confirmar o que significa. Foi mantida como está e registrada como limitação.

---

## 7. Modelo relacional normalizado

Definido em `sql/schema.sql`.

O esquema achatado foi **normalizado e desmembrado** em 8 tabelas:

| Tabela | Função |
|---|---|
| `uf` | Unidades da federação |
| `municipio` | Municípios (únicos por nome e UF) |
| `bairro` | Bairros (únicos por nome e município) |
| `endereco` | Endereço desmembrado em colunas (tipo, logradouro, número, KM, complemento, CEP), ligado ao município e, opcionalmente, ao bairro |
| `bandeira` | Nomes canônicos das bandeiras |
| `bandeira_sinonimo` | Variações de escrita ligadas à bandeira correta |
| `empresa` | Empresa dona dos postos (raiz do CNPJ), evitando repetir a razão social |
| `posto` | Cada estabelecimento (CNPJ), ligado à empresa, ao endereço e à bandeira |

Decisões: o endereço saiu da tabela de posto (desmembramento de esquema); `empresa` separa o dono do estabelecimento; o município fica em `endereco` para não repetir informação; `autorizacao` **não** é chave única, pois há números repetidos; `bairro_id` aceita nulo, pois 124 postos não têm bairro.

---

## 8. Métricas de concentração (HHI)

Script `src/metricas.py`, que funciona sobre o CSV tratado e gera os arquivos de `resultados/`.

O **HHI** é a soma dos quadrados das participações (em %) de cada concorrente no município. Vai de 0 (mercado pulverizado) a 10.000 (um único concorrente). Faixas usadas: abaixo de 1.500 (pouco concentrado), de 1.500 a 2.500 (moderado) e acima de 2.500 (muito concentrado).

- **Por rede** (empresa, raiz do CNPJ): 2.879 municípios muito concentrados, 1.269 moderados e 1.377 pouco concentrados.
- Entre os municípios com 10 postos ou mais, o mais concentrado é Flores da Cunha (RS, HHI 2.639) e os menos concentrados são Rio de Janeiro (17), São Paulo (19) e Goiânia (33).
- Maior rede: SIM REDE DE POSTOS LTDA, com 213 postos em 83 municípios.
- **1.491 municípios** têm apenas postos de bandeira branca.
- O HHI **por bandeira** (já com o dicionário aplicado) conta cada empresa de bandeira branca como concorrente separada; senão, os 22.050 postos sem marca virariam um só concorrente e inflariam o índice.

Cidades com poucos postos têm HHI alto só por serem pequenas, então a análise usa um mínimo de postos.

---

## 9. Como executar

```
pip install -r requirements.txt

python src/extract.py       # esquema original
python src/perfil.py        # exemplos de dados não conformes (pasta exemplos/)
python src/clean.py         # limpeza (gera data/processed/postos_limpo.csv)
python src/standardize.py   # endereço em colunas e sinônimos
python src/metricas.py      # HHI e rankings (pasta resultados/)
```

Rode `clean.py` antes de `standardize.py`. O arquivo original fica em `data/raw/` (não vai ao Git).

**Banco e aplicação (PostgreSQL):**

1. No pgAdmin, criar o banco `anp` e executar o arquivo `sql/schema.sql` (Query Tool, F5).
2. No terminal (PowerShell), definir a senha do PostgreSQL e carregar os dados. A senha fica só na sessão, não no código:

```
$env:DB_PASSWORD = "sua_senha"
python src/load.py             # carga das 8 tabelas (usa data/bandeiras.csv)
```

3. Conferir a carga com as consultas de `sql/validacao.sql` (contagens e HHI, comparados com `resultados/`).
4. Abrir a aplicação (mesma sessão do terminal):

```
streamlit run src/app.py
```

## 10. Estrutura do projeto

```
projeto-anp/
├── data/
│   ├── raw/             # CSV original (não editado, fora do Git)
│   └── processed/       # postos_limpo.csv (fora do Git)
├── exemplos/            # exemplos de dados não conformes e de antes/depois
├── data/bandeiras.csv   # dicionário de sinônimos de bandeira
├── resultados/          # saídas de metricas.py (referência para validar o banco)
├── sql/
│   ├── schema.sql       # esquema do banco
│   └── validacao.sql    # consultas de conferência da carga
├── src/
│   ├── extract.py       # esquema original
│   ├── perfil.py        # perfilamento
│   ├── clean.py         # limpeza
│   ├── standardize.py   # endereço e sinônimos
│   ├── metricas.py      # HHI e rankings
│   ├── load.py          # carga no PostgreSQL
│   ├── db.py            # leitura dos postos no banco
│   └── app.py           # aplicação (Streamlit)
└── requirements.txt
```

## 11. Limitações

- A base é um cadastro (sem vendas ou preços): a concentração mede presença de postos, não participação de mercado.
- 225 postos têm `COMPLEMENTO` igual a `0`, valor sem significado que **não foi tratado**.
- 776 endereços ficaram sem `tipo_logradouro` porque começam por palavras como `QI 19`, `PORTO DE AMATURA` ou `PADRE ANTONIO CORREIA DE SA`. O logradouro foi mantido inteiro.
- 49 números trazem texto (`QD 01`, `LOTE14`, `397-NW`) e não foram quebrados em mais colunas, para não perder informação.
- A base inclui autorizações de tipos diferentes (`PR`, `PF`, `AV`, `PM`, `GNV`). Todos entram nas contas, inclusive os 315 `AV`, provavelmente de aviação.
- `SP` (314 postos) é uma bandeira não identificada, mantida como veio. `RAIZEN MIME` foi unificada a `RAIZEN` por interpretação.
- A carga foi testada com PostgreSQL local. A aplicação lê o banco com as credenciais de variáveis de ambiente (`DB_PASSWORD`), por isso só roda onde o banco existir.
