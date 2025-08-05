# Usar uma imagem base do Debian com Python 3.11 já instalado
FROM python:3.11-slim

# Definir o diretório de trabalho dentro do contentor
WORKDIR /app

# Instalar o LibreOffice dentro do contentor
RUN apt-get update && apt-get install -y libreoffice-writer --no-install-recommends

# Copiar os ficheiros de requisitos e instalar as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação para dentro do contentor
COPY . .

# Expor a porta 8001 para que possamos aceder ao serviço
EXPOSE 8001

# Comando para iniciar o servidor (sem --reload para estabilidade)
CMD ["uvicorn", "generator_service:app", "--host", "0.0.0.0", "--port", "8001"]
