# main.py
# Versão 1.7 - Com Sistema de Feedback e Base de Dados SQLite

import asyncio
import uuid
import fitz  # PyMuPDF
import httpx
import json
import os
import pickle
import sqlite3
import datetime
import requests
from pydantic import BaseModel
from functools import partial
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from dotenv import load_dotenv

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document

# --- Carregar variáveis de ambiente ---
load_dotenv()

# --- Configuração da Base de Dados de Feedback ---
DB_FILE = "feedback.db"

def init_db():
    """Cria a tabela de feedback na base de dados se ela não existir."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        form_type TEXT NOT NULL,
        original_response TEXT NOT NULL,
        corrected_response TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()
    print(f"Base de dados de feedback '{DB_FILE}' inicializada com sucesso.")

# --- Inicialização da Aplicação FastAPI ---
app = FastAPI(
    title="recANALYSIS API",
    description="O cérebro por trás do assistente de análise de decisões judiciais, agora com sistema de feedback.",
    version="1.7.0"
)

@app.on_event("startup")
async def startup_event():
    """Função executada quando a aplicação inicia."""
    init_db()


# --- Configuração de CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Constantes e Configurações ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}"
POLICY_DOC_PATH = "Política Recursal.pdf"
VECTOR_STORE_PATH = "vector_store.pkl"
EMBEDDING_MODEL = "rufimelo/Legal-BERTimbau-sts-large"
GENERATOR_SERVICE_URL = "http://generator:8001"

# --- "Banco de Dados" em Memória para Jobs ---
jobs: Dict[str, Dict[str, Any]] = {}

# --- Lógica de RAG ---
def get_vector_store():
    if os.path.exists(VECTOR_STORE_PATH):
        with open(VECTOR_STORE_PATH, "rb") as f: return pickle.load(f)
    with fitz.open(POLICY_DOC_PATH) as doc:
        policy_text = "".join(page.get_text() for page in doc)
    docs = [Document(page_content=policy_text)]
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    vector_store = FAISS.from_documents(chunks, embedding=embeddings)
    with open(VECTOR_STORE_PATH, "wb") as f: pickle.dump(vector_store, f)
    return vector_store

vector_store = get_vector_store()

# --- Modelos de Dados (Pydantic) ---
class Job(BaseModel):
    job_id: str
    status: str
    data: Dict[str, Any] | None = None

class GenerationRequest(BaseModel):
    job_id: str
    form_data: Dict[str, Any]
    original_data: Dict[str, Any] # Novo campo para o feedback

# --- Endpoints da API ---

@app.get("/")
def read_root():
    return {"message": "Bem-vindo à API do recANALYSIS v1.7!"}

@app.post("/api/v1/analysis", status_code=202)
async def start_analysis(file: UploadFile = File(...), form_type: str = Form(...)):
    if not file.content_type == "application/pdf":
        raise HTTPException(status_code=400, detail="Tipo de arquivo inválido.")
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "processing", "data": None, "form_type": form_type}
    file_content = await file.read()
    asyncio.create_task(rag_ai_processing(job_id, form_type, file_content, vector_store))
    return {"job_id": job_id}

@app.get("/api/v1/analysis/{job_id}/status", response_model=Job)
def get_analysis_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabalho não encontrado.")
    return {"job_id": job_id, "status": job["status"], "data": job["data"]}

# ####################################################################
# BLOCO ALTERADO
# ####################################################################
@app.post("/api/v1/generate")
def generate_documents(request: GenerationRequest):
    job = jobs.get(request.job_id)
    if not job or job["status"] != "ready":
        raise HTTPException(status_code=400, detail="O trabalho não está pronto para geração.")

    # --- Lógica de Feedback ---
    if request.original_data != request.form_data:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO feedback (timestamp, form_type, original_response, corrected_response) VALUES (?, ?, ?, ?)",
                (
                    datetime.datetime.now().isoformat(),
                    job["form_type"],
                    json.dumps(request.original_data),
                    json.dumps(request.form_data)
                )
            )
            conn.commit()
            conn.close()
            print("Correção do utilizador guardada na base de dados de feedback.")
        except Exception as e:
            print(f"ERRO ao guardar feedback na base de dados: {e}")

    payload = {"form_type": job["form_type"], "form_data": request.form_data}
    
    # URL para comunicação INTERNA (entre serviços Docker)
    internal_generator_url = f"{GENERATOR_SERVICE_URL}/api/v1/generate-document"
    
    # URL para o BROWSER (público)
    public_download_url = "http://127.0.0.1:8001/download"

    try:
        # Usa o URL interno para a chamada
        response = requests.post(internal_generator_url, json=payload, timeout=90.0)
        response.raise_for_status()

        result = response.json()
        
        # Usa o URL público para criar os links de download
        return {
            "message": result["message"],
            "docx_url": f"{public_download_url}/{result['docx_filename']}",
            "pdf_url": f"{public_download_url}/{result['pdf_filename']}"
        }
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Não foi possível conectar ao serviço de geração: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro inesperado no serviço de geração: {str(e)}")

# --- Lógica de Processamento de IA com RAG (Esquema v2.0 - Sem alterações) ---
def get_form_fields_for_schema(form_type: str) -> Dict[str, Any]:
    schema_comum = {
        "data_publicacao": {"type": "STRING"}, "prazo_fatal": {"type": "STRING"},
        "npj": {"type": "STRING"}, "contrato_lide": {"type": "STRING"},
        "operacao_numero": {"type": "STRING"}, "data_vencimento_operacao": {"type": "STRING"},
        "autor_es": {"type": "STRING"}, "reu_s": {"type": "STRING"},
        "tipo_acao": {"type": "STRING"}, "numero_processo": {"type": "STRING"},
        "orgao_tramitacao": {"type": "STRING"}, "valor_causa": {"type": "STRING"},
        "valor_pretendido": {"type": "STRING"}, "valor_condenacao": {"type": "STRING"},
        "descricao_sucinta": {"type": "STRING", "description": "Relatório detalhado dos fatos, pedido, decisões, cumprimento de obrigação de fazer, etc."},
        "liminar_deferida": {"type": "STRING", "description": "Responder 'Sim' ou 'Não'."},
        "liminar_cumprida": {"type": "STRING", "description": "Responder 'Sim' ou 'Não'."},
        "cominacao_multa": {"type": "STRING", "description": "Responder 'Sim' ou 'Não'."},
        "multa_valor_diario": {"type": "STRING"}, "multa_limite": {"type": "STRING"},
        "litispendencia_coisa_julgada": {"type": "STRING", "description": "Responder 'Sim' ou 'Não'."},
        "documentos_anexados_check": {"type": "STRING", "description": "Responder 'Sim' ou 'Não'."},
        "escritorio_advogado_contato": {"type": "STRING", "description": "Nome do Escritório, UF, Advogado, OAB, e-mail e telefone."},
    }
    schema = {}
    if form_type == 'autodispensa':
        schema.update(schema_comum)
        schema.update({
            "recurso_objeto": {"type": "STRING", "description": "Tipo de recurso objeto da autodispensa."},
            "decisao_objeto_autodispensa": {"type": "STRING", "description": "Especificar a decisão e o número de rastreamento."},
            "materias_discutidas": {"type": "STRING", "description": "Teses jurídicas discutidas no processo."},
            "fundamento_autodispensa": {"type": "STRING", "description": "Apontar o item exato do Manual/Política que justifica a autodispensa."},
            "andamento_registrado": {"type": "STRING", "description": "Código do andamento (ex: 677 ou 703)."},
            "fundamentacao_relatorio": {"type": "STRING", "description": "Breve relato com pleitos da inicial e teor das decisões."},
            "parecer_fundamentado_autodispensa": {"type": "STRING", "description": "Parecer jurídico elaborado que ampara a autodispensa, enquadrando o caso no item do Manual."},
        })
    elif form_type in ['dispensa', 'autorizacao']:
        schema.update(schema_comum)
        schema.update({
            "tipo_recurso": {"type": "STRING", "description": "Tipo de recurso objeto da dispensa/autorização."},
            "solicitado_subsidio": {"type": "STRING", "description": "Responder 'Sim' ou 'Não'."},
            "subsidio_atendido": {"type": "STRING", "description": "Responder 'Sim' ou 'Não'."},
            "subsidio_descricao": {"type": "STRING"}, "subsidio_rastreamento": {"type": "STRING"},
            "subsidio_utilizado_defesa": {"type": "STRING", "description": "Responder 'Sim' ou 'Não'."},
            "subsidio_nao_utilizado_justificativa": {"type": "STRING"},
            "teses_defesa": {"type": "STRING", "description": "Teses jurídicas abordadas na defesa."},
            "precedente_materia_julgados": {"type": "STRING", "description": "Responder 'Não' ou 'Sim, julgado Nº XXXXX, de DD/MM/AA'."},
            "obrigacao_fazer_cumprida_descricao": {"type": "STRING", "description": "Responder 'Sim' ou 'Não' e incluir a descrição detalhada da obrigação."},
            "valor_custas_recursais": {"type": "STRING"},
        })
        if form_type == 'dispensa':
            schema['fundamentacao_dispensa'] = {"type": "STRING", "description": "Citar as circunstâncias peculiares da demanda que não recomendam a interposição do recurso."}
        else: # autorizacao
            schema['fundamentacao_autorizacao'] = {"type": "STRING", "description": "Expor os motivos para interpor o recurso, especialmente se for matéria de autodispensa, e demonstrar prequestionamento e repercussão geral se aplicável."}
    return schema

def build_rag_prompt_text(decision_text: str, relevant_policy_docs: List[Document]) -> str:
    policy_context = "\n\n".join([doc.page_content for doc in relevant_policy_docs])

    # --- PROMPT APRIMORADO v2.5 (foco em valor e Anexo I) ---
    return f"""
    Você é um assistente jurídico sênior, especialista na Política Recursal da instituição. Sua tarefa é preencher um formulário com precisão absoluta, seguindo um conjunto de regras não negociáveis.

    **ORDEM DE ANÁLISE OBRIGATÓRIA:**
    Você deve seguir os seguintes passos na ordem exata. Pare no primeiro passo que se aplicar.

    **PASSO 1: VERIFICAÇÃO DE EXCEÇÕES ABSOLUTAS (Prioridade Máxima)**
    * **Regra:** Verifique se a matéria da decisão se enquadra em alguma das exceções (PASEP, FIES, MCMV, Cédula Rural, Superendividamento, matérias residuais).
    * **Ação:** Se for uma exceção e o formulário for de 'autodispensa', preencha o campo 'fundamento_autodispensa' com: **"AVISO: VEDAÇÃO ABSOLUTA. A matéria ([nome da matéria]) não permite autodispensa."** e finalize a análise de fundamentação.

    **PASSO 2: ANÁLISE DA HIPÓTESE DE VALOR (Cenário Principal para Autodispensa)**
    * **Regra:** Se o formulário for de 'autodispensa' e o PASSO 1 não se aplicar, verifique se a **condenação patrimonial total** (excluindo juros e correção monetária) é inferior aos limites estabelecidos no "Anexo I – Hipóteses de Autodispensa Obrigatória".
    * **Ação:** Se o valor for inferior a R$5.000,00 (Juizados Especiais) ou R$10.000,00 (Justiça Comum), sua fundamentação no campo 'fundamento_autodispensa' DEVE ser: **"Conforme 13.1.3 Anexo I, inciso [I ou II], a condenação total de R$ [valor extraído] é inferior ao limite para a presente ação, sendo a autodispensa obrigatória."**

    **PASSO 3: ANÁLISE DAS DEMAIS HIPÓTESES (Apenas se os passos 1 e 2 não se aplicarem)**
    * **Regra da Hipótese Única:** Selecione **apenas UMA** outra hipótese do "Anexo I" que se aplique perfeitamente ao caso. Todas as justificativas para autodispensa devem, obrigatoriamente, originar-se deste anexo.
    * **Regra da Fundamentação Direta:** Se encontrar uma hipótese, inicie a fundamentação com a citação do item (ex: "Conforme 13.1.3 Anexo I, alínea 'x'...") e explique o enquadramento.
    * **Regra da Não-Conformação:** Se nenhuma hipótese do Anexo I se aplicar, retorne a frase exata: **"AVISO: A situação fática não se enquadra em nenhuma hipótese de autodispensa prevista no Anexo I da Política Recursal."**

    **REGRAS GERAIS ADICIONAIS:**
    * **Dados Ausentes:** Se uma informação factual não estiver na decisão, preencha o campo com **"Não consta na decisão"**. NÃO INVENTE DADOS.

    **DOCUMENTOS PARA ANÁLISE:**

    **1. CONTEXTO DA POLÍTICA RECURSAL (Fonte da Verdade para Fundamentação):**
    ---
    {policy_context}
    ---

    **2. DECISÃO JUDICIAL (Fonte dos Fatos):**
    ---
    {decision_text[:14000]}
    ---

    **TAREFA FINAL:**
    Seguindo rigorosamente a ORDEM DE ANÁLISE OBRIGATÓRIA, analise os documentos e preencha o esquema JSON a seguir.
    """

async def rag_ai_processing(job_id: str, form_type: str, file_content: bytes, vs: FAISS):
    try:
        with fitz.open(stream=file_content, filetype="pdf") as doc:
            decision_text = "".join(page.get_text() for page in doc)
        if not decision_text.strip(): raise ValueError("PDF vazio.")
        query_text = decision_text[:2000]
        relevant_docs = vs.similarity_search(query=query_text, k=3)
        prompt_text = build_rag_prompt_text(decision_text, relevant_docs)
        json_schema = get_form_fields_for_schema(form_type)
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {"type": "OBJECT", "properties": json_schema}
            }
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(GEMINI_API_URL, json=payload)
            response.raise_for_status()
        result = response.json()
        if 'candidates' in result and result['candidates']:
            extracted_data = json.loads(result['candidates'][0]['content']['parts'][0]['text'])
            jobs[job_id]["status"] = "ready"
            jobs[job_id]["data"] = extracted_data
        else:
            raise ValueError(f"Resposta inesperada da API Gemini: {result}")
    except Exception as e:
        print(f"Erro no processamento RAG do trabalho {job_id}: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["data"] = {"error": str(e)}