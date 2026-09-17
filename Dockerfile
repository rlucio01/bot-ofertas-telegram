FROM python:3.12-slim-bookworm

# Evita buffers de log e define fuso horário padrão do Brasil
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/Sao_Paulo \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Instala utilitários de sistema e fuso horário
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Instala o Chromium e todas as bibliotecas de sistema necessárias para o Playwright
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos do projeto
COPY . /app/

# Converte quebras de linha do entrypoint para LF (caso tenha sido salvo no Windows) e dá permissão
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Porta do Painel Web (opcional)
EXPOSE 8481

# Volume persistente para sessões, banco de dados SQLite e configurações dinâmicas
VOLUME ["/app/data"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["run"]
