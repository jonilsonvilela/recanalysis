# training_service.py
# Versão 1.0 - Serviço para preparar dados para Fine-Tuning do Gemini

import sqlite3
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import io

# --- Inicialização da Aplicação FastAPI ---
app = FastAPI(
    title="recANALYSIS Training Service",
    description="Serviço para extrair e formatar dados de feedback para fine-tuning de modelos de IA.",
    version="1.0.0"
)

# --- Configuração de CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Constantes ---
DB_FILE = "feedback.db"

# --- Endpoints da API ---
@app.get("/")
def read_root():
    return {"message": "Serviço de Treinamento está ativo e pronto para preparar os dados."}

@app.get("/api/v1/training-data")
def get_training_data():
    """
    Extrai os dados de feedback e os formata no padrão JSONL para fine-tuning.
    Cada linha do JSONL será um par de 'prompt' e 'completion'.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT rag_context, original_response, corrected_response FROM feedback")
        feedback_entries = cursor.fetchall()
        conn.close()

        if not feedback_entries:
            raise HTTPException(status_code=404, detail="Nenhum dado de feedback encontrado para gerar o arquivo de treinamento.")

        # Usa um buffer de texto em memória para criar o arquivo JSONL
        string_io = io.StringIO()
        for entry in feedback_entries:
            # O 'prompt' é o contexto do RAG que a IA usou.
            # A 'completion' (ou 'output') é a resposta corrigida pelo humano.
            # O fine-tuning ensinará o modelo: "Quando ver um contexto como este, gere uma resposta como esta".
            prompt_text = entry['rag_context']
            corrected_data = json.loads(entry['corrected_response'])

            # Formata a saída como um único objeto JSON por linha
            training_example = {
                "input": prompt_text,
                "output": json.dumps(corrected_data, ensure_ascii=False)
            }
            string_io.write(json.dumps(training_example, ensure_ascii=False) + '\n')

        # Retorna o conteúdo do buffer como um arquivo para download
        string_io.seek(0)
        return StreamingResponse(
            string_io,
            media_type="application/jsonl",
            headers={"Content-Disposition": "attachment; filename=training_data.jsonl"}
        )

    except sqlite3.OperationalError:
         raise HTTPException(status_code=500, detail=f"Erro ao aceder à base de dados '{DB_FILE}'. Verifique se o arquivo existe e se o serviço tem permissão de leitura.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro inesperado: {e}")