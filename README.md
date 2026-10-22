# 🏢 Real Estate Lakehouse & Scraping Platform

> Pipeline moderno de Engenharia de Dados ponta a ponta no setor imobiliário: Web Scraping resiliente, Data Lake S3/MinIO, Data Warehouse PostgreSQL, modelagem dimensional em camadas Medalhão com dbt (SCD Tipo 2), orquestração via Apache Airflow e API REST analítica de alta performance com FastAPI.

---

# 📖 Introdução

O mercado imobiliário brasileiro movimenta bilhões de reais anualmente, porém sofre de acentuada assimetria de informações, precificação volátil e dispersão de anúncios entre múltiplos portais da web (como QuintoAndar, Chaves na Mão, entre outros).

Acompanhar tendências de valorização por metro quadrado, identificar oportunidades reais de investimento (imóveis cotados significativamente abaixo da média da região) e auditar o histórico de alterações de preços exige uma arquitetura de dados robusta, capaz de operar tanto no nível de dados não estruturados brutos quanto na entrega analítica refinada.

Este projeto resolve essa dor de negócio construindo um **Data Lakehouse Moderno baseado na Arquitetura Medalhão (Bronze/Raw, Silver/Intermediate e Gold/Marts)**:
1. **Extração & Carga Bruta (EL)**: Scrapers modulares extraem anúncios de portais imobiliários e os persistem comprimidos em `.jsonl.gz` em um Data Lake S3/MinIO.
2. **Ingestão Incremental**: Uma rotina de alta performance lê os novos lotes e os grava em uma tabela de pouso com envelope `JSONB` no PostgreSQL.
3. **Transformação & Modelagem (T)**: O **dbt Core** orquestra modelos estruturados, tratando deduplicação diária, sanitização, regras de negócio e **Slowly Changing Dimensions (SCD Tipo 2)** para rastrear cada centavo de variação de preço.
4. **Camada de Consumo**: Uma **API REST construída em FastAPI** fornece endpoints paginados, filtros dinâmicos complexos e métricas agregadas por bairro para sistemas clientes e analistas.
5. **Orquestração**: O **Apache Airflow** coordena todo o pipeline diário de forma resiliente, monitorada e 100% idempotente.

---

# 🎯 Problema de Negócio

No setor imobiliário, portais e imobiliárias atualizam seus catálogos continuamente. Identificar distorções de mercado ou entender se uma redução de valor é real exige histórico confiável.

Os principais desafios enfrentados incluem:

* **Disparidade Estrutural das Fontes**: Cada portal imobiliário possui layouts, APIs internas e esquemas de dados proprietários.
* **Bloqueios e Rate Limiting**: Necessidade de contornar proteções antibot sem comprometer a estabilidade do crawler.
* **Fidelidade e Idempotência**: Impossibilidade de descartar metadados originais; reprocessar coletas repetidas do mesmo dia não pode gerar dados duplicados.
* **Rastreabilidade de Preços (SCD Type 2)**: Um imóvel pode ser anunciado por R$ 500.000, cair para R$ 450.000 duas semanas depois e ser finalizado em R$ 430.000. Modelos tradicionais sobrescrevem esse valor; o Lakehouse precisa reter a validade temporal (`valid_from` / `valid_to`).
* **Identificação de Oportunidades**: Investidores demandam respostas rápidas: *quais imóveis em determinado bairro estão pelo menos 15% abaixo do preço médio do m² local?*

O objetivo desta plataforma é transformar dados imobiliários brutos e dispersos da internet em inteligência acionável e estruturada para investidores, imobiliárias e tomadores de decisão.

---

# 🚀 Objetivos

* **Coleta Modular e Escalável**: Scrapy com Strategy Pattern desacoplado para integrar novos portais em minutos.
* **Armazenamento Não Destrutivo no Data Lake**: Envelopes brutos particionados no S3/MinIO em `.jsonl.gz` por portal, ano, mês e dia.
* **Carga Idempotente**: Loader Python gerenciando tabela de auditoria (`raw.lake_ingestion_log`) e inserção transacional no PostgreSQL.
* **Modelagem Medalhão com dbt Core**:
  * `stg_anuncios`: Extração e tipagem estrita de colunas do `JSONB`.
  * `int_anuncios_diarios`: Deduplicação intra-batch (Nível 1) e filtros de sanidade física.
  * `snp_historico_precos`: Snapshot SCD Tipo 2 rastreando alterações de valores e status.
  * `dim_anuncios_ativos`: Tabela analítica da camada Gold com flags de oportunidade de mercado.
  * `fct_metricas_bairro_diarias`: Fato agregada diária com métricas consolidadas (preço médio, mediana, valor por m²).
* **Consumo via FastAPI Assíncrona**: SQLAlchemy 2.0 (AsyncIO), pooler connection management (`NullPool`) e validação estrita com Pydantic v2.
* **Orquestração Contínua**: DAG diária no Apache Airflow orquestrando o pipeline de ponta a ponta com quality gates automatizados.

---

# 🏗 Arquitetura

```text
              Portais Imobiliários (Web)
        [QuintoAndar]       [Chaves na Mão]
               │                   │
               └─────────┬─────────┘
                         ▼
             Scrapy Spider Adaptativo
         (Strategy Pattern + Middlewares)
                         │
                         ▼
          MinIO / Amazon S3 (Data Lake)
         Bucket: raw-imoveis (.jsonl.gz)
                         │
                         ▼
        Incremental Loader (Python / COPY)
           Auditoria: raw.lake_ingestion_log
                         │
                         ▼
         PostgreSQL Landing (raw.landing_anuncios)
                         │
  ┌──────────────────────┴──────────────────────┐
  │                                             │
  ▼                                             ▼
dbt Staging (stg_anuncios)               Apache Airflow
  │                                      (Orquestrador)
  ▼                                             │
dbt Silver (int_anuncios_diarios)               │
  │                                             │
  ├──────────────────────┐                      │
  ▼                      ▼                      │
dbt Snapshot (SCD2)   dbt Gold (Marts)          │
(snp_historico_precos)  (dim_anuncios_ativos)   │
                         (fct_metricas_bairro)  │
                                │               │
                                ▼               │
                   PostgreSQL Data Warehouse    │
                                │               │
                                └───────┬───────┘
                                        ▼
                                FastAPI Backend
                            (SQLAlchemy 2.0 Async)
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
                 Interactive Swagger UI        Sistemas de Consumo
                 (/docs / redoc)               (Investidores & BI)
```

Imagem Ilustrativa
<img width="1672" height="941" alt="Arquitetura Lakehouse Imobiliária e Scraping" src="https://github.com/user-attachments/assets/e10fd6fd-dea8-4c56-b79d-0b539dd4e950" />


---

# ⚙ Tecnologias Utilizadas

### Linguagens
* **Python 3.11+**
* **SQL (ANSI & PostgreSQL Dialect)**

### Coleta & Web Scraping
* **Scrapy 2.11+**: Framework assíncrono de alto rendimento.
* **Strategy Pattern**: Arquitetura desacoplada onde cada portal possui sua própria implementação de requisição e parsing.
* **Fake-UserAgent & Browser Headers Middleware**: Rotação dinâmica de User-Agents realistas e headers modernos de navegadores (`Sec-Ch-Ua`, `Accept-Language`).

### Armazenamento & Data Lake
* **MinIO / Amazon S3**: Storage de objetos distribuído compatível com a API S3.
* **Gzip & JSONL**: Compressão de lotes brutos com redução de ~80% de tráfego de rede e armazenamento.
* **Particionamento Hive-like**: `portal=.../year=.../month=.../day=.../batch.jsonl.gz`.

### Data Warehouse & Banco de Dados
* **PostgreSQL 16 (Neon Serverless)**: Banco analítico com suporte avançado a dados semiestruturados (`JSONB`), índices B-Tree e connection pooling via pgBouncer.

### Transformação & Modelagem
* **dbt Core 1.8+ (`dbt-postgres`)**: Orquestração de SQL modular, Staging Views, Silver Tables, Gold Marts e Snapshots SCD Tipo 2.
* **Quality Tests**: Validação de chaves substitutas (`surrogate_key`), unicidade, não-nulidade e intervalos numéricos.

### Camada de Consumo / API REST
* **FastAPI**: Framework web assíncrono moderno e de alta performance.
* **SQLAlchemy 2.0 (AsyncIO)**: Mapeamento objeto-relacional assíncrono com suporte nativo a `NullPool` para connection poolers em nuvem.
* **Asyncpg**: Driver assíncrono de PostgreSQL para Python mais rápido do mercado.
* **Pydantic v2**: Serialização ultrarrápida e validação estrita de esquemas JSON.

### Orquestração & Monitoramento
* **Apache Airflow 2.9.3**: Orquestração de workflows complexos via DAGs declarativas em Python com `LocalExecutor`.
* **Loguru**: Logging estruturado e colorido para rastreabilidade de execuções.

### Containers & DevOps
* **Docker & Docker Compose**: Empacotamento de toda a infraestrutura (Airflow Webserver, Scheduler, Postgres, etc.).
* **Unittest & Pytest**: Suíte automatizada cobrindo 100% dos fluxos e componentes do repositório.

---

# 📂 Estrutura do Projeto

```text
real-estate-lakehouse/
│
├── api/                             # Camada de Consumo: API REST FastAPI
│   ├── core/                        # Configurações centrais, ambiente e engine assíncrono
│   │   ├── config.py
│   │   └── database.py
│   ├── models/                      # Modelos ORM SQLAlchemy mapeando as tabelas Gold e Snapshots
│   │   └── imoveis.py
│   ├── routers/                     # Endpoints da aplicação
│   │   ├── analytics.py             # Rotas de métricas, oportunidades e histórico SCD2
│   │   └── imoveis.py               # Rotas de consulta de imóveis com filtros dinâmicos
│   ├── schemas/                     # Schemas de validação e serialização Pydantic v2
│   │   └── imoveis.py
│   └── main.py                      # Ponto de entrada FastAPI com middlewares de CORS e tratamento de erros
│
├── dags/                            # Orquestração: DAGs do Apache Airflow
│   └── dag_imoveis_pipeline.py      # DAG diária unificando Scrapy -> Ingestão -> dbt -> dbt test
│
├── dbt_imoveis/                     # Transformação: Projeto dbt Core
│   ├── models/
│   │   ├── staging/                 # Camada Staging: extração e tipagem JSONB (views)
│   │   │   ├── schema.yml
│   │   │   └── stg_anuncios.sql
│   │   ├── intermediate/            # Camada Silver: deduplicação Nível 1 e sanitização (tabelas)
│   │   │   ├── schema.yml
│   │   │   └── int_anuncios_diarios.sql
│   │   └── marts/                   # Camada Gold: dimensões ativas e fatos analíticas
│   │       ├── schema.yml
│   │       ├── dim_anuncios_ativos.sql
│   │       └── fct_metricas_bairro_diarias.sql
│   ├── snapshots/                   # Rastreamento temporal SCD Tipo 2
│   │   └── snp_historico_precos.sql
│   ├── profiles.yml                 # Credenciais de conexão parametrizadas via variáveis de ambiente
│   └── dbt_project.yml
│
├── scrapers/                        # Camada de Coleta: Scrapy modular
│   ├── imoveis_scraper/
│   │   ├── spiders/                 # Spiders adaptativos de extração
│   │   │   ├── imoveis_spider.py
│   │   │   └── check_headers_spider.py
│   │   ├── strategies/              # Strategy Pattern para cada portal alvo
│   │   │   ├── base_strategy.py
│   │   │   ├── quintoandar_strategy.py
│   │   │   └── chavesnamao_strategy.py
│   │   ├── middlewares.py           # Injeção de headers e rotação de User-Agents
│   │   ├── pipelines.py             # Compressão Gzip e upload de lotes brutos ao Data Lake S3
│   │   └── settings.py
│   └── scrapy.cfg
│
├── scripts/                         # Ingestão & Utilitários
│   ├── lake_to_postgres_loader.py   # Loader incremental idempotente S3 -> PostgreSQL Landing
│   └── test_connections.py          # Script de validação de conectividade com S3 e Neon
│
├── tests/                           # Suíte de Testes Automatizados (65 testes)
│   ├── test_airflow_dag.py
│   ├── test_airflow_setup.py
│   ├── test_api_analytics.py
│   ├── test_api_imoveis.py
│   ├── test_api_setup.py
│   ├── test_dbt_quality_tests.py
│   ├── test_dbt_setup.py
│   ├── test_int_anuncios_diarios.py
│   ├── test_lake_loader.py
│   ├── test_marts_models.py
│   ├── test_raw_ddl.py
│   ├── test_snp_historico_precos.py
│   ├── test_spider_strategies.py
│   ├── test_stg_anuncios.py
│   └── test_storage_pipeline.py
│
├── .env.example                     # Modelo de variáveis de ambiente com documentação
├── docker-compose.yml               # Orquestração dos serviços (Airflow Webserver, Scheduler, Postgres)
├── requirements.txt                 # Dependências Python do projeto
└── README.md
```

---

# 📊 Modelagem Lakehouse (Medalhão)

A modelagem de dados foi desenhada seguindo os princípios de ELT moderno e arquitetura Medalhão:

## 1. Camada Bronze (Raw Lake & Landing Zone)
* **Bucket S3 (`raw-imoveis`)**: Armazena os lotes brutos comprimidos no formato `.jsonl.gz`. Os objetos são organizados de forma particionada por portal, ano, mês e dia (`portal=quinto_andar/year=2026/month=10/day=21/...`).
* **Tabela de Pouso (`raw.landing_anuncios`)**: Armazena os registros com coluna `JSONB`, preservando exatamente todos os atributos retornados pelos sites, além dos metadados de rastreabilidade (`source_portal`, `batch_id`, `scraped_at`).
* **Tabela de Auditoria (`raw.lake_ingestion_log`)**: Registra cada arquivo lido do S3 (chave, hash, tamanho, total de registros e timestamp de ingestão), garantindo que nenhum lote seja carregado em duplicidade.

## 2. Camada Staging (Views)
* **`stg_anuncios`**: Extrai campos estruturados do `JSONB` via operadores nativos do PostgreSQL (`->>`). Cria uma chave substituta determinística (`surrogate_key`) calculada por hash MD5:

  ```math
  \text{surrogate}\_\text{key} = \text{MD5}(\text{source}\_\text{portal} \parallel \text{portal}\_\text{listing}\_\text{id})
  ```

* Padroniza nomes de colunas, formatações de data e tipagem estrita (preço, condomínio, IPTU, área útil, quartos, banheiros, vagas, latitude e longitude).

## 3. Camada Silver / Intermediate (Tables)
* **`int_anuncios_diarios`**: Tabela materializada com deduplicação técnica de coleta (Nível 1). Se o mesmo imóvel for coletado múltiplas vezes no mesmo dia (ex: reexecução da spider), uma janela analítica `ROW_NUMBER() OVER (PARTITION BY surrogate_key, data_coleta ORDER BY scraped_at DESC)` seleciona exclusivamente o estado mais recente.
* Aplica filtros de sanidade física: descarta anúncios com valores absurdos, áreas zeradas ou coordenadas geográficas inválidas.

## 4. Snapshots Históricos (SCD Tipo 2)
* **`snp_historico_precos`**: Snapshot gerenciado pelo dbt utilizando a estratégia `check` nas colunas `preco`, `taxa_condominio`, `iptu` e `status_ativo`.
* Adiciona automaticamente os metadados de ciclo de vida do registro:
  * `dbt_valid_from`: Timestamp do início de vigência daquele preço.
  * `dbt_valid_to`: Timestamp do encerramento da vigência (ou `NULL` para o registro atual).
  * `dbt_updated_at`: Momento da captura da alteração.

## 5. Camada Gold / Marts (Analytics)
* **`dim_anuncios_ativos`**: Dimensão com todos os imóveis atualmente ativos no mercado, enriquecida com a média de preço/m² do bairro e a flag de oportunidade:
  * `status_oportunidade`: Classifica o anúncio como `ABAIXO_DA_MEDIA` quando o preço do m² for inferior à média local, ou `NA_MEDIA` / `ACIMA_DA_MEDIA`.
  * `diferenca_percentual_bairro`: Cálculo analítico do desconto ou ágio percentual frente ao mercado da região.
* **`fct_metricas_bairro_diarias`**: Fato agregada por bairro e data contendo total de anúncios, preço médio, mediana de valor, desvio padrão, preço médio por m² e contagem de oportunidades ativas.

---

# 🔄 Pipeline Ponta a Ponta

## 1. Coleta de Dados Brutos (Scrapy & Strategy Pattern)
O crawler é acionado indicando a cidade, estado, tipo de negócio e os portais desejados:
```bash
scrapy crawl imoveis -a portal=all -a city=sao-paulo -a state=sp -a business_type=venda
```
Cada estratégia de portal (`QuintoAndarStrategy`, `ChavesNaMaoStrategy`) processa os seletores e envelopes de resposta específicos, empacotando os itens em uma estrutura padrão. O pipeline `MinIOStoragePipeline` comprime o lote em Gzip e grava diretamente no bucket S3.

## 2. Ingestão Incremental no Banco (Python Loader)
O script `lake_to_postgres_loader.py` entra em ação:
* Lista novos arquivos no bucket do Data Lake.
* Cruza as chaves contra a tabela de auditoria `raw.lake_ingestion_log`.
* Descompacta o lote em memória (`BytesIO`) e realiza a carga em massa (`COPY` / `executemany`) na tabela `raw.landing_anuncios`.

## 3. Transformação e Modelagem Dimensional (dbt)
O dbt executa o pipeline em sequência:
1. `dbt run`: Atualiza Staging, Silver e Marts Gold.
2. `dbt snapshot`: Atualiza os snapshots SCD Tipo 2, capturando novos preços e fechando o intervalo dos anteriores.
3. `dbt test`: Quality gates avaliando unicidade, integridade e validações de negócio.

## 4. Orquestração Diária (Apache Airflow)
A DAG `dag_imoveis_lakehouse_pipeline` executa todos os dias às 06:00 UTC (03:00 Horário de Brasília) de forma automática:

<img width="1882" height="873" alt="Captura de tela 2026-10-22 104347" src="https://github.com/user-attachments/assets/3b4e45ec-3697-41dd-b03c-c8e9cb104b28" />

---

# 🌐 Camada de Consumo: API REST (FastAPI)

A camada de consumo expõe os dados das tabelas Gold e Snapshots via endpoints REST assíncronos de baixa latência:

### Principais Endpoints

| Método | Rota | Descrição |
| :---: | :--- | :--- |
| `GET` | `/health` | Healthcheck do serviço e validação de conectividade com o banco. |
| `GET` | `/api/v1/imoveis` | Listagem paginada de imóveis com **11 filtros dinâmicos** (bairro, preço min/max, quartos min, banheiros min, vagas min, área min/max, status de oportunidade) e ordenação dinâmica. |
| `GET` | `/api/v1/imoveis/{id}` | Detalhes completos de um imóvel específico por `surrogate_key` ou `portal_listing_id`. |
| `GET` | `/api/v1/oportunidades` | Listagem das melhores oportunidades de investimento, ordenadas pelo maior desconto percentual frente à média do bairro. |
| `GET` | `/api/v1/metricas/bairros` | Painel consolidado com estatísticas agregadas por bairro (preço médio, mediana, preço/m² e contagem de oportunidades). |
| `GET` | `/api/v1/historico-precos/{id}` | Histórico completo de evolução de preços do anúncio via SCD Tipo 2, indicando vigência e variação percentual. |

### Exemplo de Resposta: `/api/v1/oportunidades`

```json
{
  "total": 42,
  "page": 1,
  "page_size": 2,
  "total_pages": 21,
  "items": [
    {
      "surrogate_key": "c4ca4238a0b923820dcc509a6f75849b",
      "source_portal": "quinto_andar",
      "portal_listing_id": "894561234",
      "titulo": "Apartamento com 2 quartos à venda em Moema",
      "bairro": "Moema",
      "cidade": "São Paulo",
      "preco": 620000.0,
      "area_util_m2": 70.0,
      "preco_m2": 8857.14,
      "preco_medio_m2_bairro": 11500.0,
      "diferenca_percentual_bairro": -22.98,
      "status_oportunidade": "ABAIXO_DA_MEDIA"
    }
  ]
}
```

---

# ✅ Qualidade dos Dados

A confiabilidade das informações é garantida por testes automatizados em múltiplas barreiras:

1. **Testes Unitários e de Integração (Python `unittest`)**:
   - **65 testes automatizados** cobrindo Web Scraper, Middlewares, Pipelines S3, Loader Incremental, Modelos dbt, Endpoints FastAPI e DAGs do Airflow.
2. **Quality Gates do dbt (`dbt test`)**:
   - `unique` e `not_null` em chaves primárias e substitutas.
   - `accepted_values` em status de anúncios e tipos de negócio.
   - Testes de intervalos de valores para preços e áreas úteis.
   - Integridade de relacionamentos entre tabelas de dimensões e fatos.
3. **Resiliência Assíncrona**:
   - Uso de `NullPool` no SQLAlchemy para compatibilidade total com o connection pooler da Neon (pgBouncer).
   - Políticas de retries automáticos com backoff exponencial para variações de latência em bancos de dados em nuvem.

---

# ▶ Como Executar

### 1. Clonar o Repositório

```bash
git clone https://github.com/Riansito/real-estate-lakehouse.git
cd real-estate-lakehouse
```

### 2. Configurar o Ambiente Virtual e Variáveis

Crie o arquivo `.env` baseado no modelo [.env.example](file:///home/rianf/projetos/scraping-apartamentos/.env.example):

```bash
cp .env.example .env
```

Preencha suas credenciais de banco de dados (Neon / PostgreSQL) e chaves S3/MinIO no arquivo `.env`.

Instale as dependências locais:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Subir os Serviços com Docker Compose

Para subir a infraestrutura completa do Apache Airflow e seus serviços auxiliares:

```bash
docker compose up -d
```

### 4. Executar os Componentes Manualmente (Opcional)

**Executar o Web Scraper:**
```bash
cd scrapers
scrapy crawl imoveis -a portal=all -a city=sao-paulo -a max_pages=3
cd ..
```

**Executar a Ingestão no PostgreSQL:**
```bash
python scripts/lake_to_postgres_loader.py --portal all
```

**Executar o dbt:**
```bash
cd dbt_imoveis
dbt run --profiles-dir . --project-dir .
dbt snapshot --profiles-dir . --project-dir .
dbt test --profiles-dir . --project-dir .
cd ..
```

**Iniciar o Servidor FastAPI:**
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Executar toda a Suíte de Testes:**
```bash
python -m unittest discover -s tests
```

---

# 🔗 Acompanhe as Interfaces

* **FastAPI Swagger Interativo**: `http://localhost:8000/docs`
* **FastAPI Redoc Alternativo**: `http://localhost:8000/redoc`
* **Apache Airflow Webserver**: `http://localhost:8080` (Usuário: `airflow` / Senha: `airflow`)

---

# 📈 Melhorias Futuras

* Implementação de modelos de Machine Learning (Precificação Hedônica) para prever o valor justo de imóveis com base em características estruturais.
* Integração de novos portais imobiliários (Zap Imóveis, Viva Real e Imovelweb).
* Camada de Georreferenciamento avançada com PostGIS para cálculos de raio de proximidade de metrôs e parques.
* Cache de consultas analíticas em Redis para redução de latência nos endpoints de métricas de bairros.
* Dashboard interativo em Streamlit ou Metabase conectado diretamente às tabelas Gold.

---

# 👨‍💻 Autor

**Rian**

Estudante de Sistemas de Informação na UFPB, com foco em Engenharia de Dados e Analytics.

Este projeto foi desenvolvido com o propósito de consolidar conhecimentos práticos em Arquitetura de Data Lakehouse moderna, pipelines ELT idempotentes, dbt, modelagem dimensional com SCD Tipo 2, desenvolvimento de APIs assíncronas de alta performance e orquestração de missões críticas com Apache Airflow.
