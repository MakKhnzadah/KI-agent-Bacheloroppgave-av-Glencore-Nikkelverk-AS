import os


class AgentService:

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider
        self.max_input_chars = int(os.getenv("AGENT_MAX_INPUT_CHARS", "16000"))

    def process_document(self, system_prompt: str, content: str):
        trimmed_content = content
        if len(content) > self.max_input_chars:
            # Keep prompts bounded so uploads do not block for very large documents.
            trimmed_content = (
                content[: self.max_input_chars]
                + "\n\n[... dokumentet ble forkortet for raskere AI-behandling ...]"
            )

        full_prompt = f"""
{system_prompt}

Document:
{trimmed_content}
"""

        return self.llm_provider.generate(full_prompt)