# Manual Completo do Bot de Ofertas para Telegram 🤖🔥

Este guia reúne todas as funcionalidades, comandos, regras de negócio, integrações de afiliados e dicas práticas para você extrair o máximo do seu bot de ofertas rodando na sua VPS ou localmente.

---

## 📑 Sumário
1. [Como o Bot Funciona por Baixo dos Panos](#1-como-o-bot-funciona-por-baixo-dos-panos)
2. [As 3 Plataformas e Como Geram Comissões](#2-as-3-plataformas-e-como-geram-comissões)
3. [Comandos e Interações no Telegram](#3-comandos-e-interações-no-telegram)
4. [O Conversor Manual de Links](#4-o-conversor-manual-de-links)
5. [Configurações e Filtros Avançados (`config.yaml`)](#5-configurações-e-filtros-avançados-configyaml)
6. [O Painel Web Funciona na VPS?](#6-o-painel-web-funciona-na-vps)
7. [Dicas de Ouro e Melhores Práticas](#7-dicas-de-ouro-e-melhores-práticas)
8. [Manutenção, Logs e Resolução de Problemas](#8-manutenção-logs-e-resolução-de-problemas)

---

## 1. Como o Bot Funciona por Baixo dos Panos

O bot opera através de um pipeline em 5 etapas sequenciais a cada ciclo:

```text
[1. Coleta]  ──>  [2. Filtros]  ──>  [3. Seleção]  ──>  [4. Links Afiliados]  ──>  [5. Postagem]
  (ML, Shopee,     (Desconto,       (Top N por          (Gera links           (Foto + Preço
    Amazon)         Anti-repetição)  desconto/nichos)    com sua tag/cookie)    + Botão de compra)
```

1. **Coleta**: Varre as páginas de promoções ativas de cada plataforma habilitada.
2. **Filtros**:
   - Elimina produtos sem título ou sem preço.
   - Verifica o banco de dados (`ofertas.db`): se já foi postado nos últimos $X$ dias (`nao_repetir_dias`), é descartado.
   - Valida o desconto mínimo (ex: só aceita 25% ou mais).
   - Valida preços mínimos/máximos e elimina produtos com palavras proibidas (ex: "capinha", "película").
3. **Seleção Inteligente**:
   - Ordena pelo maior desconto percentual.
   - Faz alternância de plataformas (não posta 3 ofertas seguidas da mesma loja).
   - Elimina variações do mesmo item (ex: se tem iPhone preto e iPhone branco, escolhe apenas um).
4. **Geração de Links de Afiliado**:
   - Gera o link comissionado apenas das ofertas aprovadas finais (economizando chamadas de API e processamento do navegador).
5. **Postagem no Canal**:
   - Envia a imagem do produto em alta resolução com a legenda formatada (preço riscado "De", preço "Por", % de desconto, selos como *Frete Grátis*, *Pix*, *Prime*, etc.) e um botão inline interativo `"🛒 Pegar oferta"`.
   - Aguarda uma pausa configurável entre um post e outro (`espacamento_segundos`) para não inundar o canal.

---

## 2. As 3 Plataformas e Como Geram Comissões

### 💛 Mercado Livre
- **Origem das ofertas**: Scraping automatizado da página oficial `mercadolivre.com.br/ofertas`.
- **Geração de comissão**: O Mercado Livre não tem API pública de afiliados. O bot utiliza o Playwright com um navegador Chromium rodando nos bastidores com a sua sessão logada (`data/ml_profile`). Ele acessa a API interna do Linkbuilder do Mercado Livre e gera links oficiais no formato encurtado `https://meli.la/...`.
- **Duração da sessão**: O login dura semanas ou meses. Se expirar, o bot te avisa no privado do Telegram.

### 🧡 Shopee
- **Origem das ofertas**: Open API oficial de Afiliados da Shopee via requisições GraphQL (`productOfferV2`).
- **Geração de comissão**: Autenticação com assinatura criptográfica `SHA256` usando seu `SHOPEE_APP_ID` e `SHOPEE_APP_SECRET`. A API já devolve o `offerLink` exclusivo atrelado à sua conta de afiliado.

### 📦 Amazon
- **Origem das ofertas**:
  - *Modo Oficial*: Se preenchidas as credenciais da Creators API (`AMAZON_CREDENTIAL_ID` e `SECRET`), busca diretamente pelo catálogo oficial da Amazon.
  - *Modo Inteligente (Fallback)*: Caso sua conta ainda não tenha acesso à Creators API, o bot faz scraping das páginas de ofertas por departamento e injeta a sua tag de associado (`?tag=sua_tag-20`) em cada produto.

---

## 3. Comandos e Interações no Telegram

Fale com o seu bot no privado do Telegram (apenas o seu usuário configurado em `TELEGRAM_OWNER_ID` tem permissão para os comandos administrativos):

| Comando | O que faz |
|---|---|
| `/status` | Mostra o total de ofertas já postadas no banco, quais plataformas estão ativas, o intervalo de minutos e o desconto mínimo. |
| `/ciclo` | Força a execução imediata de uma rodada de garimpo. Ideal para testar ou forçar postagens sem esperar o temporizador. |
| `/id` | Mostra o seu `User ID` pessoal. Se você encaminhar qualquer post do seu canal para o bot, ele te mostra o `Chat ID` do canal. |
| `/start` | Exibe o menu inicial de ajuda com a lista de comandos. |

---

## 4. O Conversor Manual de Links

Além das postagens 100% automáticas, você pode usar o bot como um **conversor instantâneo de links**:

1. Você encontrou uma promoção boa enquanto navegava no celular ou computador.
2. Copie o link do produto (Mercado Livre, Shopee ou Amazon).
3. **Cole o link no privado do bot no Telegram**.
4. O bot processa o link em poucos segundos e te envia uma prévia com:
   - Imagem do produto;
   - Título oficial;
   - Preços ("De / Por") e desconto;
   - Botão **`🛒 Pegar oferta`** (com o seu link comissionado para conferir);
   - Botão **`✅ Postar no canal`**;
   - Botão **`🗑 Descartar`**.
5. Clicando em **Postar no canal**, a oferta é publicada imediatamente no seu canal com o layout padrão e registrada no banco de dados.

---

## 5. Configurações e Filtros Avançados (`config.yaml`)

O arquivo `/opt/bot-ofertas/config.yaml` controla o comportamento do robô:

```yaml
geral:
  intervalo_minutos: 45        # A cada quantos minutos o bot busca novas ofertas
  max_posts_por_ciclo: 3       # Máximo de produtos postados em cada ciclo
  espacamento_segundos: 120    # Pausa de 2 minutos entre um post e outro no canal
  nao_repetir_dias: 7          # Não reposta o mesmo produto dentro de 7 dias
  horario_ativo: "08:00-23:00" # Horário de funcionamento (deixe "" para rodar 24h)

filtros:
  desconto_minimo: 25          # Só aceita ofertas com 25% ou mais de desconto
  preco_minimo: 20             # Ignora produtos abaixo de R$ 20,00 (evita bugigangas)
  preco_maximo: 5000           # 0 = sem limite máximo
  palavras_bloqueadas:         # Ignora produtos que contenham estes termos no título
    - capinha
    - película
    - cabo usb
    - adesivo
```

> [!TIP]
> **Como focar em um Nicho específico:**
> Se o seu canal for só de tecnologia, games, moda ou casa, você pode preencher as listas de categorias em `config.yaml` ou selecionar os nichos no arquivo `data/nichos.json`.

---

## 6. O Painel Web Funciona na VPS?

**Sim, ele está totalmente pronto no container!** Porém, no passo a passo que fizemos, colocamos a variável:

```yaml
APP_MODE=run
```

### Por que configuramos `APP_MODE=run`?
1. **Mais leve e rápido**: Consome menos memória RAM da VPS.
2. **Máxima segurança**: Não expõe portas HTTP desprotegidas na internet.
3. **Você não precisa do painel**: Como vimos, 100% das ações diárias (status, forçar ciclo, converter links manuais) são feitas com muito mais conforto diretamente pelo Telegram.

### Quer usar o Painel Web na VPS com Traefik?
Se no futuro você quiser acessar `https://ofertas.meudominio.com` no seu navegador:
1. Altere a variável para `APP_MODE=painel`.
2. Adicione os labels do Traefik contidos no arquivo [`portainer-stack-swarm.yml`](portainer-stack-swarm.yml).
3. O painel subirá com o botão de ligar/desligar e o seletor de nichos visual.

---

## 7. Dicas de Ouro e Melhores Práticas

1. **Aviso Legal Obrigatório no Canal**:
   - Os programas de afiliados (especialmente a Amazon) exigem que canais de divulgação informem aos usuários que utilizam links comissionados.
   - Coloque na descrição do seu canal:
     > *"Participamos de programas de afiliados. Ao comprar através dos nossos links, podemos receber uma comissão sem qualquer custo adicional para você."*
2. **Evite Repetições Excessivas**:
   - Mantenha `nao_repetir_dias: 7`. Isso garante que o canal tenha sempre variedade e não fique postando o mesmo fone de ouvido todo dia.
3. **Espaçamento entre Posts**:
   - Deixar `espacamento_segundos: 120` evita que o Telegram bloqueie seu bot por flood de mensagens e dá tempo para os membros visualizarem cada promoção com calma.
4. **Volume de Postagens**:
   - Um bom ritmo para canais com alto engajamento é entre 15 e 35 ofertas por dia. O padrão (3 ofertas a cada 45 minutos) se encaixa perfeitamente nesse volume.

---

## 8. Manutenção, Logs e Resolução de Problemas

### Como ver o que o bot está fazendo em tempo real
No seu Portainer:
- Acesse **Services** → `bot-ofertas_bot` → clique no ícone de **Logs**.
- Lá você acompanha cada página varrida, quantas ofertas foram encontradas e quais foram aprovadas.

### Se o Mercado Livre parar de gerar links (Sessão Expirada)
Se os cookies do Mercado Livre precisarem ser renovados:
1. O bot enviará uma mensagem no seu privado: `⚠️ Mercado Livre parou de gerar links: Sessão expirou`.
2. No seu computador Windows, se precisar logar de novo:
   ```powershell
   uv run python -m ofertas ml-login
   ```
   *(Ou se já estiver logado, basta exportar com: `uv run python -m ofertas ml-export`)*
3. Envie o arquivo leve de sessão (`ml_state.json`, apenas 9 KB) direto para a VPS:
   ```powershell
   scp data/ml_state.json usuario@ip_da_vps:/opt/bot-ofertas/data/
   ```
4. No Portainer, clique no botão **Restart** do serviço. O bot agora renova os cookies automaticamente no `ml_state.json` a cada ciclo!

### Como reiniciar o bot
No Portainer, vá em **Services** → marque a caixa do `bot-ofertas_bot` → clique em **Restart**.
