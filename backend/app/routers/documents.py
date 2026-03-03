from fastapi import APIRouter, UploadFile, File
from app.document_processing.document_parsing import parse_document
from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider
from app.agents.structuring_agents import STRUCTURING_AGENT_PROMPT

router = APIRouter(prefix="/documents", tags=["documents"])

llm_provider = OllamaProvider()
agent = AgentService(llm_provider)

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()

    processed_text = parse_document(file.filename, content)

    suggestions = agent.process_document(STRUCTURING_AGENT_PROMPT, processed_text)

    return {
        "suggestions": suggestions,
        "status": "pending_approval"
    }