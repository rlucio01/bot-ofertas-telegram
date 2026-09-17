# Guia de Implantação 24x7 na VPS (Ubuntu 24 + Docker Swarm + Portainer + Traefik) 🚀

Este guia ensina o passo a passo completo para colocar o **Bot de Ofertas** rodando 24 horas por dia, 7 dias por semana na sua VPS, sem precisar manter o computador ligado.

---

## 📋 Visão Geral da Arquitetura

Na VPS com Docker Swarm, o bot roda dentro de um container isolado:
- **Playwright + Chromium**: Executa em modo *headless* dentro do Linux com aceleração e flags seguras para containers.
- **Persistência**: O banco de ofertas (`ofertas.db`) e os cookies autenticados do Mercado Livre (`ml_profile`) ficam salvos na pasta `/opt/bot-ofertas/data` da VPS, sobrevivendo a reinicializações ou atualizações do container.
- **Traefik**: Faz o roteamento automático do seu domínio (ex: `https://ofertas.meudominio.com`) com certificado SSL/TLS (HTTPS) gratuito do Let's Encrypt diretamente para o painel web.

---

## 🎯 Escolha o Seu Modo de Operação

Você pode rodar o container de duas maneiras (configurável pela variável `APP_MODE`):

| Modo | Descrição | Quando usar |
|---|---|---|
| **`APP_MODE=painel`** (Padrão) | Inicia o **Painel Web na porta 8481** (com Traefik) e liga o bot automaticamente em segundo plano. | Se você quer abrir o painel pelo navegador para ver logs, trocar nichos e disparar testes. |
| **`APP_MODE=run`** | Roda **somente o Bot 24x7 no Telegram**. Não precisa de portas abertas nem domínio no Traefik. | Se você quer a máxima simplicidade e economia de memória (apenas postagens automáticas). |

---

## 🛠️ Passo 1: Preparar os Dados no seu PC Local (Windows)

Como você já fez o login do Mercado Livre no seu computador e o bot já está funcionando, vamos aproveitar essa sessão para não precisar fazer login na VPS!

No seu Windows, a pasta do projeto contém:
1. `data/ml_profile/` (cookies e sessão logada do Mercado Livre)
2. `data/ofertas.db` (banco de dados SQLite para não repetir ofertas já postadas)
3. `data/nichos.json` (caso tenha selecionado nichos no painel)
4. `config.yaml` (suas configurações de intervalos e categorias)
5. `.env` (seus tokens e chaves)

---

## 📦 Passo 2: Criar a Pasta Persistente na VPS e Transferir os Dados

Acesse sua VPS via SSH (PowerShell ou terminal):

```bash
# 1. Crie o diretório de persistência na VPS
sudo mkdir -p /opt/bot-ofertas/data

# 2. Defina as permissões para o seu usuário (substitua pelo seu usuário na VPS, ex: ubuntu ou root)
sudo chown -R $USER:$USER /opt/bot-ofertas
```

Agora, no PowerShell do seu Windows (dentro da pasta do projeto `d:\PROJETOS\bot-ofertas-telegram`), envie o `ml_profile`, o banco de dados e as configurações:

```powershell
# Compacte a pasta data para facilitar o envio
Compress-Archive -Path data\* -DestinationPath dados_bot.zip -Force

# Envie para a VPS via SCP (ajuste 'usuario' e 'ip_da_vps')
scp dados_bot.zip usuario@ip_da_vps:/opt/bot-ofertas/
scp config.yaml usuario@ip_da_vps:/opt/bot-ofertas/
```

De volta ao terminal da sua VPS:

```bash
cd /opt/bot-ofertas
unzip dados_bot.zip -d data/
rm dados_bot.zip

# Verifique se o ml_profile e ofertas.db estão lá:
ls -la /opt/bot-ofertas/data
```

> [!NOTE]
> Se a pasta `pw-browsers` for junto, não tem problema, mas o container Linux usará sua própria versão do Chromium em `/ms-playwright` otimizada para o Ubuntu.

---

## 🔨 Passo 3: Construir a Imagem Docker

Você pode construir a imagem diretamente na VPS ou subir para um registry (Docker Hub / GitHub Container Registry).

### Opção A: Build Direto na VPS (Mais Rápido e Fácil)

Envie a pasta do projeto para a VPS ou faça o clone do seu repositório:

```bash
cd /opt/bot-ofertas-src  # pasta com o código e o Dockerfile
docker build -t bot-ofertas-telegram:latest .
```

O build instalará o Python 3.12, todas as dependências, o Playwright e o Chromium nativo do Linux.

---

## 🚢 Passo 4: Criar a Stack no Portainer (Docker Swarm)

1. Abra o painel do seu **Portainer**.
2. No menu lateral, acesse **Swarm** (ou seu cluster) → **Stacks**.
3. Clique em **+ Add stack**.
4. Em **Name**, defina: `bot-ofertas`.
5. Selecione **Web editor** e cole o conteúdo do arquivo [`portainer-stack-swarm.yml`](portainer-stack-swarm.yml).

### Configurar Variáveis de Ambiente no Portainer:
Logo abaixo do editor de texto, na seção **Environment variables**, clique em **+ Add environment variable** e adicione as suas chaves:

| Variável | Exemplo de Valor | Obrigatório |
|---|---|---|
| `DOMAIN` | `ofertas.seudominio.com` | Sim (se usar painel com Traefik) |
| `CERT_RESOLVER` | `letsencrypt` (ou o nome do seu resolver no Traefik) | Sim |
| `TELEGRAM_BOT_TOKEN` | `123456789:ABCdefGHI...` | Sim |
| `TELEGRAM_CHAT_ID` | `-1001234567890` (ou `@seucanal`) | Sim |
| `TELEGRAM_OWNER_ID` | `987654321` | Sim |
| `ML_ETIQUETA` | `sua_etiqueta_linkbuilder` | Sim (para ML) |
| `AMAZON_TAG` | `seunome-20` | Sim (para Amazon) |
| `AMAZON_CREDENTIAL_ID` | `...` | Opcional |
| `AMAZON_CREDENTIAL_SECRET` | `...` | Opcional |
| `SHOPEE_APP_ID` | `123456` | Se usar Shopee |
| `SHOPEE_APP_SECRET` | `abc...` | Se usar Shopee |
| `APP_MODE` | `painel` ou `run` | Sim |

> [!IMPORTANT]
> **Rede do Traefik:** Verifique no seu Portainer em **Networks** qual é o nome exato da rede overlay externa do seu Traefik (geralmente `traefik-public`, `proxy` ou `traefik_public`). Se o nome for diferente de `traefik-public`, altere na stack (tanto em `networks:` quanto em `traefik.docker.network=`).

6. Clique no botão **Deploy the stack**.

---

## 🔒 Passo 5: Protegendo o Painel Web (Recomendado)

O painel web permite disparar testes e ver logs. Se você publicou o painel em `ofertas.seudominio.com`, é altamente recomendado colocar uma senha nele via middleware do Traefik.

Para gerar um usuário e senha (exemplo: usuário `admin` e senha `senha_secreta`):

```bash
# Na sua VPS, execute:
sudo apt-get install -y apache2-utils
echo $(htpasswd -nb admin senha_secreta) | sed -e s/\\$/\\$\\$/g
```

Você receberá algo como: `admin:$$apr1$$X7z8...`.

No arquivo `portainer-stack-swarm.yml`, descomente as linhas de BasicAuth do Traefik:
```yaml
- "traefik.http.middlewares.botofertas-auth.basicauth.users=admin:$$apr1$$X7z8..."
- "traefik.http.routers.botofertas.middlewares=botofertas-auth"
```
E atualize a stack no Portainer!

---

## ✅ Passo 6: Verificação e Monitoramento

1. **Acompanhando os Logs:**
   - No Portainer, vá em **Services** → `bot-ofertas_bot-ofertas` → **Logs**.
   - Você verá o ciclo agendado, o carregamento das fontes ativas e a confirmação do bot ativo.
2. **Testando pelo Telegram:**
   - Abra o Telegram e mande uma mensagem no privado do seu bot:
     - `/status` — Mostra o total de postagens e situação das fontes.
     - `/ciclo` — Dispara um ciclo de busca imediatamente para testar as postagens no canal.
     - Cole qualquer link do Mercado Livre, Shopee ou Amazon para ver o conversor instantâneo.
3. **Acessando o Painel (se ativo):**
   - Acesse `https://ofertas.seudominio.com` no seu navegador.
   - Veja os logs ao vivo, os nichos selecionados e o status das credenciais.

---

## 💡 Dúvidas Frequentes e Dicas

### E se a sessão do Mercado Livre expirar no futuro?
O Mercado Livre mantém a sessão ativa por semanas/meses. Se um dia ela expirar:
1. No seu computador local, rode: `uv run python -m ofertas ml-login`.
2. Faça o login e feche o navegador.
3. Envie a pasta `data/ml_profile` atualizada para a VPS:
   ```powershell
   scp -r data/ml_profile usuario@ip_da_vps:/opt/bot-ofertas/data/
   ```
4. Reinicie o serviço no Portainer.

### Por que `replicas: 1` no Docker Swarm?
O Telegram usa conexões long-polling (`getUpdates`). Se você colocar mais de 1 réplica, as duas instâncias tentarão ler a fila ao mesmo tempo e o Telegram bloqueará com o erro `409 Conflict`. Portanto, mantenha sempre **1 réplica**.
