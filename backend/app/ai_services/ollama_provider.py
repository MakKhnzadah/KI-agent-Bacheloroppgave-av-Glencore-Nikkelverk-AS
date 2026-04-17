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

    def _request_generate(self, prompt: str, options_override: dict | None = None) -> requests.Response:
        options = {
            "temperature": 0,
            "num_predict": self.num_predict,
        }

        # Some Ollama APIs support `format: "json"` as a top-level request field.
        # Allow callers to pass it via options_override.
        request_format = None
        if options_override:
            if "format" in options_override:
                request_format = options_override.get("format")
            for k, v in options_override.items():
                if v is None:
                    continue
                if k == "format":
                    continue
                options[k] = v

        # Safety clamp: avoid extreme generation sizes that can hang the server.
        try:
            options["num_predict"] = int(options.get("num_predict", self.num_predict))
        except Exception:
            options["num_predict"] = self.num_predict
        options["num_predict"] = max(128, min(options["num_predict"], 16384))

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        if request_format is not None:
            payload["format"] = request_format

        return requests.post(
            self.url,
            json=payload,
            timeout=self.timeout_s,
        )

    def generate(self, prompt: str, *, options: dict | None = None) -> str:
        last_error = None
        for _attempt in range(self.max_retries + 1):
            try:
                response = self._request_generate(prompt, options_override=options)
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