from fastapi import APIRouter
from pydantic  import BaseModel

from app.ai_services.agent_service import AgentService
from app.ai_services.ollama_provider import OllamaProvider
from app.agents.structuring_agents import STRUCTURING_AGENT_PROMPT

router = APIRouter(prefix="/agent", tags=["AI Agent"])

class DocumentRequest(BaseModel):
    text: str

llm = OllamaProvider()
agent = AgentService(llm)

@router.post("/process")
def process_document(request: DocumentRequest):
    result = agent.process_document(STRUCTURING_AGENT_PROMPT, request.text)
    return {"result": result}