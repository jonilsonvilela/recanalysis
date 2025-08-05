recANALYSIS - Assistente Inteligente para Análise Jurídica
recANALYSIS é uma aplicação web de ponta projetada para otimizar o fluxo de trabalho de advogados e analistas jurídicos. A ferramenta utiliza um modelo de linguagem avançado (Google Gemini), enriquecido com a técnica de Geração Aumentada por Recuperação (RAG), para analisar decisões judiciais em formato PDF e preencher automaticamente formulários complexos, como súmulas de recurso.

✨ Funcionalidades Principais
Upload Inteligente: Faça o upload de decisões judiciais em formato .pdf diretamente na interface.

Análise por IA com RAG: O sistema utiliza um modelo de linguagem para ler o documento e, com base numa "Política Recursal" interna (RAG), extrai as informações contextuais necessárias.

Preenchimento Automático: A IA preenche automaticamente o formulário web correspondente ao tipo de súmula selecionada (Dispensa, Autodispensa, Autorização).

Validação Humana: O utilizador pode revisar, corrigir e validar todos os campos preenchidos pela IA, garantindo a precisão final do documento.

Aprendizagem Contínua: As correções feitas pelos utilizadores são armazenadas numa base de dados de feedback, criando um ciclo virtuoso para o futuro re-treino e aprimoramento do modelo.

Geração de Documentos: Após a confirmação, o sistema gera automaticamente os documentos finais nos formatos .docx e .pdf, prontos para download.

🏗️ Arquitetura
O projeto é construído sobre uma arquitetura de microsserviços, orquestrada com Docker Compose, garantindo escalabilidade, isolamento e manutenibilidade.

Frontend (index.html): Uma interface de página única (SPA) construída com HTML, TailwindCSS e JavaScript puro. É a porta de entrada para a interação do utilizador.

Serviço de API (api): O cérebro da aplicação. Um serviço FastAPI (main.py) responsável por:

Gerir os uploads de ficheiros.

Orquestrar o processo de análise com a IA (RAG + Gemini).

Armazenar e recuperar o feedback dos utilizadores numa base de dados SQLite.

Comunicar com o serviço de geração de documentos.

Serviço de Geração (generator): Um serviço FastAPI (generator_service.py) dedicado a uma única tarefa:

Receber os dados validados.

Preencher um template .docx usando a biblioteca docxtpl.

Converter o .docx gerado para .pdf usando uma instância do LibreOffice que corre dentro do seu próprio contentor.

🛠️ Stack Tecnológica
Backend: Python 3.11, FastAPI

Frontend: HTML5, TailwindCSS, JavaScript (Vanilla)

IA & RAG: LangChain, Google Gemini, HuggingFace Embeddings (rufimelo/Legal-BERTimbau-sts-large), Faiss (Vector Store)

Geração de Documentos: DocxTemplater, LibreOffice

Base de Dados (Feedback): SQLite

Containerização e Orquestração: Docker, Docker Compose

🚀 Instalação e Execução
Para executar este projeto localmente, você precisa ter o Docker e o Docker Compose instalados.

1. Clone o Repositório:

Bash

git clone https://github.com/seu-usuario/recanalysis.git
cd recanalysis
2. Configure as Variáveis de Ambiente:

Crie um ficheiro chamado .env na raiz do projeto, copiando o conteúdo do exemplo abaixo.

Snippet de código

# .env
GEMINI_API_KEY="SUA_CHAVE_DE_API_DO_GEMINI_AQUI"
3. Adicione a Política Recursal:

Coloque o seu documento de política, nomeado como Política Recursal.pdf, na raiz do projeto. Este documento será usado para criar a base de conhecimento do sistema RAG.

4. Construa e Inicie os Contentores:

Abra o terminal na raiz do projeto e execute o seguinte comando:

Bash

docker-compose up --build
Este comando irá descarregar as imagens base, instalar todas as dependências Python, e iniciar os serviços. A primeira execução pode demorar alguns minutos.

5. Aceda à Aplicação:

Após a conclusão do processo, abra o seu navegador e aceda a:

➡️ http://127.0.0.1:8000/ (para verificar a API)

➡️ Acesse a interface principal do seu projeto, que deve ser servida em um dos seus contêineres ou localmente

📖 Como Usar
Faça o Upload: Na página inicial, arraste ou clique para selecionar o ficheiro PDF da decisão judicial.

Escolha o Formulário: Selecione o tipo de súmula que deseja gerar (Dispensa, Autodispensa ou Autorização).

Execute a Análise: Clique no botão "Executar Análise". O sistema irá processar o documento e preencher os campos.

Valide os Dados: Na segunda etapa, revise todos os campos preenchidos pela IA. Faça as correções necessárias diretamente nos campos de texto.

Confirme e Gere: Após a revisão, clique em "Confirmar e Gerar".

Faça o Download: Na etapa final, clique nos botões para baixar os documentos nos formatos .docx e .pdf.

📂 Estrutura do Projeto
/
├── .dockerignore         # Ficheiros a serem ignorados pelo Docker
├── .env                  # Ficheiro para chaves de API (NÃO versionar)
├── .gitignore            # Ficheiros a serem ignorados pelo Git
├── docker-compose.yml    # Orquestra os serviços da aplicação
├── Dockerfile            # Define a imagem para o serviço 'generator'
├── Dockerfile.api        # Define a imagem para o serviço 'api'
├── feedback.db           # Base de dados SQLite para feedback
├── generator_service.py  # Lógica do serviço de geração de documentos
├── index.html            # Frontend da aplicação
├── main.py               # Lógica do serviço principal da API e RAG
├── Política Recursal.pdf # Documento base para o sistema RAG
├── requirements.txt      # Dependências Python
└── templates/            # Pasta com os templates .docx
    └── ...