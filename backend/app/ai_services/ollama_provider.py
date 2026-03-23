import os
import requests

class OllamaProvider:
    def __init__(self, model: str = "llama3:8b"):
        self.model = os.getenv("OLLAMA_MODEL", model)
        self.url = os.getenv("OLLAMA_GENERATE_URL", "http://localhost:11434/api/generate")
        self.debug = os.getenv("OLLAMA_DEBUG", "0").strip() in {"1", "true", "True", "yes", "YES"}
        # Ollama defaults can be quite short; allow overriding generation length.
        # `num_predict` roughly maps to max tokens to generate.
        try:
            self.num_predict = int(os.getenv("OLLAMA_NUM_PREDICT", "4096").strip())
        except ValueError:
            self.num_predict = 4096
        self.num_predict = max(128, min(self.num_predict, 16384))

    def generate(self, prompt: str) -> str:
        response = requests.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": self.num_predict,
                }
            },
            timeout=120,
        )
        if self.debug:
            print("STATUS:", response.status_code)
            print("BODY:", response.text)

        response.raise_for_status()
        return response.json()["response"]