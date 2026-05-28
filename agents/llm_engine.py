"""LLM Engine — Kiro primary, DeepSeek fallback."""
import json
import logging
import httpx
from typing import Optional

logger = logging.getLogger("monkeyking.llm")


class LLMEngine:
    """
    Handles all LLM calls. Primary: Kiro (via agentic chat context).
    Fallback: DeepSeek API when running standalone.
    """

    def __init__(self, config: dict):
        self.primary = config.get("primary", "kiro")
        self.fallback = config.get("fallback", "deepseek")
        ds = config.get("deepseek", {})
        self.ds_api_key = ds.get("api_key", "")
        self.ds_model = ds.get("model", "deepseek-chat")
        self.ds_base_url = ds.get("base_url", "https://api.deepseek.com/v1")
        self._available = bool(self.ds_api_key)
        if not self._available:
            logger.warning(
                "No DeepSeek API key configured. LLM calls will return empty strings "
                "in standalone mode. Set DEEPSEEK_API_KEY in .env or use Kiro agentic chat."
            )

    @property
    def is_available(self) -> bool:
        """Check if an LLM backend is configured and usable."""
        return self._available

    async def generate(self, prompt: str, system: str = "", temperature: float = 0.3) -> str:
        """Generate text using available LLM. Falls back to DeepSeek if Kiro unavailable."""
        if self.ds_api_key:
            return await self._call_deepseek(prompt, system, temperature)
        # No API key — return empty so callers can handle gracefully
        logger.warning("LLM generate() called without API key — returning empty string")
        return ""

    async def _call_deepseek(self, prompt: str, system: str, temperature: float) -> str:
        """Call DeepSeek API with retry."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.ds_base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.ds_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.ds_model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": 4096,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"DeepSeek API attempt {attempt + 1}/3 failed: {e}. Retrying in {wait}s...")
                import asyncio
                await asyncio.sleep(wait)

        logger.error(f"DeepSeek API failed after 3 attempts: {last_error}")
        return ""
