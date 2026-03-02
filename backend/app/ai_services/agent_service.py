class AgentService:

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def process_document(self,system_prompt:str, content: str):

        full_prompt = f"""
{system_prompt}

Document:
{content}
"""

        return self.llm_provider.generate(full_prompt)