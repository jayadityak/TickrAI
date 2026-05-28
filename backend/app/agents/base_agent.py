import asyncio
import json
import logging
from abc import ABC, abstractmethod

from openai import AsyncOpenAI, RateLimitError

from ..config import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    name: str
    index: int

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def run(self, ticker: str, company_data: dict) -> dict:
        raw_data = await self.fetch_data(ticker, company_data)
        prompt = self.build_prompt(ticker, company_data, raw_data)
        response = await self.call_llm(prompt)
        return self.parse_response(response)

    @abstractmethod
    async def fetch_data(self, ticker: str, company_data: dict) -> dict:
        pass

    @abstractmethod
    def build_prompt(self, ticker: str, company_data: dict, raw_data: dict) -> str:
        pass

    async def call_llm(self, prompt: str, max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an expert equity research analyst. Provide detailed, "
                                "data-driven analysis in a clear, professional format. Use specific "
                                "numbers and cite sources where possible. Respond in well-structured JSON."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,
                )
                return response.choices[0].message.content or "{}"
            except RateLimitError as e:
                wait = min(2 ** attempt * 5, 30)
                logger.warning("Rate limited on %s (attempt %d), waiting %ds", self.name, attempt + 1, wait)
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait)
                else:
                    raise

    def parse_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"error": "Failed to parse response", "raw": response}
