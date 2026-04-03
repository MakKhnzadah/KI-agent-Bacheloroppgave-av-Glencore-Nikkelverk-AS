import os


class AgentService:

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider
        self.max_input_chars = int(os.getenv("AGENT_MAX_INPUT_CHARS", "16000"))

    def process_document(
        self,
        system_prompt: str,
        content: str,
        *,
        max_input_chars: int | None = None,
        llm_options: dict | None = None,
    ):
        trimmed_content = content
        max_chars = self.max_input_chars if max_input_chars is None else max(1000, int(max_input_chars))
        if len(content) > max_chars:
            # Keep prompts bounded so uploads do not block for very large documents.
            trimmed_content = (
                content[: max_chars]
                + "\n\n[... dokumentet ble forkortet for raskere AI-behandling ...]"
            )

        full_prompt = f"""
{system_prompt}

Document:
{trimmed_content}
"""

        return self.llm_provider.generate(full_prompt, options=llm_options)