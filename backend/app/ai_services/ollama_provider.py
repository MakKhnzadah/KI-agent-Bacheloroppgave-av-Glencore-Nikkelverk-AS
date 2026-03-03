from urllib import response

import requests

class OllamaProvider:
    def __init__(self, model: str = "llama3:8b" ):
        self.model = model
        self.url = "http://localhost:11434/api/generate"

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
        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        response.raise_for_status()
        return response.json()["response"]