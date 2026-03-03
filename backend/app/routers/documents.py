from fastapi import APIRouter, UploadFile, File
from app.document_processing.document_parsing import parse_document
from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider

router = APIRouter(prefix="/documents", tags=["documents"])

llm_provider = OllamaProvider()
agent = AgentService(llm_provider)

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()

    processed_text = parse_document(file.filename, content)

    system_prompt = """
You are a knowledge base assistant.
Analyze the document and suggest structured updates
in Markdown with YAML metadata.
"""

    suggestions = agent.process_document(system_prompt, processed_text)

    return {
        "suggestions": suggestions,
        "status": "pending_approval"
    }