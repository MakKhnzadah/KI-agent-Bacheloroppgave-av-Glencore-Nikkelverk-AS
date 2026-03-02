from ollama_provider import OllamaProvider

llm = OllamaProvider()

result = llm.generate("Say hello in one sentence, and say it in norwegian")
print(result)