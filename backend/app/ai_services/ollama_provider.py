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
        try:
            self.timeout_s = float(os.getenv("OLLAMA_GENERATE_TIMEOUT_S", "240").strip())
        except ValueError:
            self.timeout_s = 240.0
        self.timeout_s = max(30.0, min(self.timeout_s, 1800.0))
        try:
            self.max_retries = int(os.getenv("OLLAMA_GENERATE_RETRIES", "1").strip())
        except ValueError:
            self.max_retries = 1
        self.max_retries = max(0, min(self.max_retries, 3))

    def _request_generate(self, prompt: str) -> requests.Response:
        return requests.post(
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
            timeout=self.timeout_s,
        )

    def generate(self, prompt: str) -> str:
        last_error = None
        for _attempt in range(self.max_retries + 1):
            try:
                response = self._request_generate(prompt)
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = exc
                response = None
        else:
            raise last_error  # pragma: no cover

        if response is None:
            raise RuntimeError("Ollama generation request did not produce a response")

        if self.debug:
            print("STATUS:", response.status_code)
            print("BODY:", response.text)

        response.raise_for_status()
        return response.json()["response"]