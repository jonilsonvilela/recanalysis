# generator_service.py
# Este serviço deve ser executado num contentor Docker que tenha o LibreOffice instalado.
#
# Para rodar este servidor:
# 1. Instale as dependências: pip install fastapi "uvicorn[standard]" docxtpl
# 2. Crie uma pasta 'templates' com os seus ficheiros .docx (ex: 'dispensa.docx').
#    - Edite os templates para incluir tags Jinja2, como {{ numero_processo }}.
# 3. Crie uma pasta 'output' para os ficheiros gerados.
# 4. Execute no seu terminal: uvicorn generator_service:app --reload

import os
import uuid
import subprocess
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any

from docxtpl import DocxTemplate

# --- Inicialização da Aplicação FastAPI ---
app = FastAPI(
    title="recANALYSIS Document Generator",
    description="Serviço para gerar documentos .docx e .pdf a partir de templates.",
    version="1.1.0"
)

# --- Configuração de Pastas ---
TEMPLATE_FOLDER = "templates"
OUTPUT_FOLDER = "output"
os.makedirs(TEMPLATE_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- Modelos de Dados (Pydantic) ---
class GenerationPayload(BaseModel):
    form_type: str
    form_data: Dict[str, Any]

# --- Mapeamento de Tipos de Formulário para Ficheiros de Template ---
TEMPLATE_MAPPING = {
    "dispensa": "13.4.1. Súmula de Dispensa de Recurso.docx",
    "autodispensa": "13.3. Súmula de Autodispensa de Recurso.docx",
    "autorizacao": "13.4.1. Súmula de Autorização para Interposição de Recurso.docx"
}

# --- Endpoints da API ---

@app.get("/")
def read_root():
    return {"message": "Serviço de Geração de Documentos está ativo."}

@app.post("/api/v1/generate-document", status_code=201)
def create_document(payload: GenerationPayload):
    """
    Gera um ficheiro .docx e um .pdf a partir de dados e um tipo de formulário.
    """
    template_name = TEMPLATE_MAPPING.get(payload.form_type)
    if not template_name:
        raise HTTPException(status_code=400, detail="Tipo de formulário inválido.")

    template_path = os.path.join(TEMPLATE_FOLDER, template_name)
    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail=f"Ficheiro de template não encontrado: {template_name}")

    unique_id = str(uuid.uuid4())
    docx_filename = f"{payload.form_type}_{unique_id}.docx"
    docx_filepath = os.path.join(OUTPUT_FOLDER, docx_filename)

    # O contexto são os dados do formulário recebidos diretamente.
    # As chaves no seu template .docx devem corresponder às chaves no form_data.
    # Ex: {{ data_publicacao }}, {{ numero_processo }}, etc.
    context = payload.form_data

    try:
        doc = DocxTemplate(template_path)
        doc.render(context)
        doc.save(docx_filepath)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao renderizar o template DOCX: {e}")

    # Converte o DOCX gerado para PDF usando LibreOffice
    try:
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", OUTPUT_FOLDER, docx_filepath],
            check=True,
            timeout=60
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Comando 'soffice' (LibreOffice) não encontrado. Este serviço deve ser executado num ambiente com LibreOffice instalado.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Falha na conversão para PDF: {e}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="A conversão para PDF demorou demasiado tempo (timeout).")

    pdf_filename = docx_filename.replace(".docx", ".pdf")
    pdf_filepath = os.path.join(OUTPUT_FOLDER, pdf_filename)

    if not os.path.exists(pdf_filepath):
         raise HTTPException(status_code=500, detail="Ficheiro PDF não foi criado após a conversão.")

    return {
        "message": "Documentos gerados com sucesso.",
        "docx_filename": docx_filename,
        "pdf_filename": pdf_filename
    }

@app.get("/download/{file_name}")
def download_file(file_name: str):
    """
    Endpoint para fazer o download dos ficheiros gerados.
    """
    file_path = os.path.join(OUTPUT_FOLDER, file_name)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=file_name, media_type='application/octet-stream')
    raise HTTPException(status_code=404, detail="Ficheiro não encontrado.")
