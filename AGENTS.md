# AGENTS.md — Guia de Arquitetura e Contexto para Agentes de IA 🤖

Este arquivo serve como **contexto técnico mestre** para qualquer Agente de IA (Antigravity, Cursor, Claude Dev, Copilot, ChatGPT, etc.) que for trabalhar neste repositório no futuro. Leia este documento antes de propor ou executar qualquer alteração.

---

## 1. 📌 Visão Geral do Projeto

* **Nome do Projeto**: `bot-ofertas-telegram`
* **Objetivo**: Um bot autônomo para Telegram que garimpa promoções no **Mercado Livre**, **Shopee** e **Amazon**, aplica os links comissionados de afiliado do proprietário e publica os posts automaticamente em um canal ou grupo do Telegram.
* **Modos de Operação**:
  1. **Automático (24x7)**: Roda em ciclos agendados (`apscheduler`), filtrando por desconto, preço, horário e evitando repetições via banco SQLite.
  2. **Conversor Interativo**: Permite que o proprietário envie links de produtos no privado do bot para gerar prévias com foto, preço e botões inline de postagem rápida.
  3. **Painel Web Local (Opcional)**: Interface web leve (`painel.py` / porta 8481) para gerenciamento visual de nichos, credenciais e testes.

---

## 2. 🛠️ Stack Tecnológica

* **Linguagem**: Python 3.12+
* **Gerenciamento de Pacotes**:
  * Local (Windows): Gerenciado via `uv` (`pyproject.toml`, `uv.lock`).
  * Container / VPS: `pip` utilizando `requirements.txt`.
* **Bibliotecas Principais**:
  * `python-telegram-bot[job-queue]`: Framework assíncrono para o Telegram (usando long polling `getUpdates`).
  * `playwright`: Automação de navegador Chromium headless (usado para o Linkbuilder do Mercado Livre).
  * `requests`, `beautifulsoup4`, `lxml`: Web scraping rápido das listagens de ofertas.
  * `PyYAML`, `python-dotenv`: Carregamento de configurações (`config.yaml`) e segredos (`.env`).
  * `sqlite3`: Banco de dados nativo anti-repetição (`data/ofertas.db`).
* **Ambiente de Produção**:
  * VPS Ubuntu 24 com Docker Swarm, Portainer e Traefik.
  * Mapeamento de persistência de host em `/opt/bot-ofertas/data`.

---

## 3. 📂 Estrutura de Arquivos e Responsabilidades

```text
d:\PROJETOS\bot-ofertas-telegram/
├── .env.example              # Template de credenciais e chaves
├── config.yaml               # Parâmetros operacionais (intervalos, filtros, categorias)
├── requirements.txt          # Dependências pip para o Docker
├── pyproject.toml / uv.lock  # Configuração uv para desenvolvimento local
├── Dockerfile                # Imagem Python 3.12 com Chromium Linux e tzdata
├── entrypoint.sh             # Script de inicialização (chaveia entre 'run' e 'painel')
├── docker-compose.yml        # Configuração para Docker local / standalone
├── portainer-stack-swarm.yml # Stack oficial para Docker Swarm com Traefik
├── MANUAL_DO_BOT.md          # Manual de usuário e comandos do Telegram
├── DEPLOY_VPS_PORTAINER.md   # Guia detalhado de deploy na VPS
├── PAINEL.bat / run.bat      # Scripts rápidos de execução no Windows
│
├── data/                     # PERSISTÊNCIA (IGNORADA NO GIT, MONTADA VIA VOLUME NO DOCKER)
│   ├── ml_profile/           # Perfil persistente do Chrome com cookies/sessão logada do ML
│   ├── ofertas.db            # Banco SQLite (tabela 'postadas')
│   ├── nichos.json           # Categorias ativas salvas pelo painel
│   └── pw-browsers/          # Chromium do Windows (local uv, não usado no Docker)
│
└── ofertas/                  # PACOTE PRINCIPAL PYTHON
    ├── __main__.py / main.py # CLI dispatcher (check, run, painel, ciclo, testar, etc.)
    ├── bot_interativo.py     # Telegram Application, handlers (/status, /ciclo, links) e JobQueue
    ├── config.py             # Parser do .env + config.yaml + validações
    ├── db.py                 # Funções SQLite (ja_postada, registrar, total_postadas)
    ├── formatter.py          # Montagem do layout HTML dos posts (preço De/Por, emojis, etc.)
    ├── models.py             # Dataclass 'Oferta' (plataforma, id, preco, url_afiliado, etc.)
    ├── nichos.py             # Mapeamento de categorias e buscas entre as 3 plataformas
    ├── painel.py             # Servidor HTTP nativo do painel web
    ├── painel_html.py        # Template HTML/CSS/JS do painel
    ├── pipeline.py           # Ciclo autônomo: coletar -> filtrar -> escolher -> afiliar -> postar
    ├── telegram_poster.py    # Funções de envio de fotos e mensagens com botões inline
    ├── utils.py              # User-agent, sessão requests, parse de moeda brasileira
    └── sources/              # MÓDULOS ESPECÍFICOS DE CADA FONTE
        ├── __init__.py       # Factory de fontes (detectar_fonte)
        ├── mercadolivre.py   # Scraping ML + Linkbuilder Playwright
        ├── shopee.py         # Open API GraphQL oficial Shopee
        └── amazon.py         # Creators API oficial + Fallback Scraping com tag
```

---

## 4. 🔄 Pipeline de Execução (`ofertas/pipeline.py`)

A cada ciclo automático agendado (padrão a cada 45 min):
1. **`dentro_do_horario()`**: Checa se a hora atual está dentro de `geral.horario_ativo` (ex: `08:00-23:00`). Se for madrugada, o ciclo é abortado.
2. **`coletar()`**:
   - Shopee: Chama `shopee.buscar_ofertas()`.
   - Amazon: Chama `amazon.buscar_ofertas()`.
   - Mercado Livre: Chama `mercadolivre.buscar_ofertas()` (apenas scraping inicial, sem gerar links ainda).
3. **`filtrar()`**:
   - Rejeita itens já existentes no SQLite dentro de `nao_repetir_dias`.
   - Rejeita itens com desconto inferior a `desconto_minimo`.
   - Aplica filtros de preço mínimo/máximo e palavras bloqueadas.
4. **`escolher(n)`**:
   - Ordena por maior % de desconto.
   - Alterna entre as lojas para não postar ofertas consecutivas da mesma plataforma.
   - Elimina variações do mesmo produto via `_chave_similar()`.
5. **Geração de Links de Afiliado (Mercado Livre)**:
   - Os links de afiliado do ML são gerados **apenas para as ofertas que passaram no filtro final** via `mercadolivre.gerar_links_afiliado()` (otimização para evitar sobrecarga de chamadas ao Linkbuilder).
6. **`postar_oferta()`**:
   - Envia imagem e caption formatada em HTML para o canal do Telegram configurado.
   - Aguarda `espacamento_segundos` entre os envios.
   - Registra no banco de dados via `db.registrar(oferta)`.

---

## 5. ⚠️ Regras Críticas e Gotchas para Agentes

Ao editar ou estender este projeto, preste atenção aos seguintes pontos:

### 1. Sessão do Mercado Livre (`data/ml_profile`)
* O Mercado Livre não possui API pública aberta para afiliados. Ele depende da API interna `createLink` do Linkbuilder, que só responde quando autenticada pelos cookies da sessão.
* Essa sessão fica salva no diretório `data/ml_profile`.
* Em containers Linux, o Chromium **DEVE** rodar com as flags:
  `["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]`.
* Nunca apague ou sobrescreva `data/ml_profile` sem necessidade.

### 2. Docker Swarm e Telegram Polling (`replicas: 1`)
* O bot conecta na API do Telegram via polling contínuo (`getUpdates`).
* **NUNCA** configure mais de 1 réplica (`replicas: 1`). Se duas instâncias rodarem simultaneamente com o mesmo token, o Telegram retornará `HTTP 409 Conflict`.

### 3. Fuso Horário (`TZ=America/Sao_Paulo`)
* A regra de `horario_ativo` usa a hora local do sistema. No Dockerfile e nos arquivos de compose/stack, `TZ=America/Sao_Paulo` deve ser mantido para que os ciclos respeitem o horário brasileiro.

### 4. Segurança do Painel Web
* O painel web (`painel.py`) não possui autenticação própria por senha.
* No modo VPS padrão de produção, o container roda com `APP_MODE=run` (sem abrir servidor web).
* Se for ativado com `APP_MODE=painel` na internet, deve ser protegido obrigatoriamente por Traefik BasicAuth ou middleware de autenticação.

### 5. Git e Arquivos Sensíveis
* O arquivo `.env` e a pasta `data/` contêm credenciais reais e cookies de sessão. Eles **NUNCA** devem ser commitados no Git. O `.gitignore` já está configurado para barrá-los.

---

## 6. 🧪 Como Rodar e Testar

### Localmente (com `uv` no Windows):
```powershell
uv sync
uv run python -m ofertas check        # Valida credenciais e dependências
uv run python -m ofertas testar ml    # Testa garimpo no ML sem postar
uv run python -m ofertas testar shopee
uv run python -m ofertas testar amazon
uv run python -m ofertas ciclo        # Roda um ciclo completo
uv run python -m ofertas run          # Roda o bot interativo
uv run python -m ofertas painel       # Abre o painel web
```

### Na VPS (Docker / Portainer):
* Build da imagem: `docker build -t bot-ofertas-telegram:latest .`
* Logs no Portainer: **Services** → `bot-ofertas_bot` → **Logs**
* Testes via Telegram:
  * `/status`: Situação do bot e número de postagens.
  * `/ciclo`: Força uma rodada manual de postagem.
  * Colar uma URL de produto no privado do bot para testar o conversor.

---

## 7. 🚀 Playbook para Novas Features

* **Adicionar uma Nova Plataforma (ex: Magalu, AliExpress)**:
  1. Crie o scraper em `ofertas/sources/novaplataforma.py` implementando `buscar_ofertas() -> list[Oferta]` e `converter(url) -> Oferta`.
  2. Registre a detecção de link no `ofertas/sources/__init__.py`.
  3. Adicione a coleta no `ofertas/pipeline.py` (função `coletar()`).
  4. Adicione as chaves/tags correspondentes no `ofertas/config.py` e `.env.example`.
  5. Adicione o emoji/nome formatado em `ofertas/formatter.py` (`_PLATAFORMA`).
