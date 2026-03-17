import os

import requests

class OllamaProvider:
    def __init__(self, model: str = "llama3:8b" ):
        self.model = os.getenv("OLLAMA_MODEL", model)
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.url = f"{base}/api/generate"

    def generate(self, prompt: str) -> str:
        response = requests.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0
                }
            }
        )

        # Keep terminal output clean by default.
        # If you need to debug Ollama responses, set: OLLAMA_DEBUG=1
        if os.getenv("OLLAMA_DEBUG") == "1":
            print("STATUS:", response.status_code)
            print("BODY:", response.text)

        response.raise_for_status()
        return response.json()["response"]