import os
from typing import Dict, List, Optional
from langchain.llms.base import LLM
import httpx


class LiteLLM(LLM):
    def __init__(self, api_url: str, model: str, api_key: str = None, user_id: str = None, tier: str = None, **kwargs):
        self.api_url = api_url
        self.model = model
        self.api_key = api_key or os.getenv("LITELLM_API_KEY")
        self.user_id = user_id
        self.tier = tier
        self.kwargs = kwargs

    @property
    def _llm_type(self) -> str:
        return "litellm"

    async def _call(self, prompt: str, stop: List[str] = None, functions: List[Dict] = None) -> Dict:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            headers.update({"X-User-ID": self.user_id, "X-Tier": self.tier})  # Pass metadata for rate limiting
            payload = {
                "model": self.model,
                "prompt": prompt,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.kwargs.get("temperature", 0.7)
            }
            if functions:
                payload["functions"] = functions
                payload["function_call"] = "auto"
            if stop:
                payload["stop"] = stop
            response = await client.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    async def acompletion(self, messages: List[Dict], functions: List[Dict] = None, **kwargs) -> Dict:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        headers.update({"X-User-ID": self.user_id, "X-Tier": self.tier})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7)
        }
        if functions:
            payload["functions"] = functions
            payload["function_call"] = "auto"
        async with httpx.AsyncClient() as client:
            response = await client.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()