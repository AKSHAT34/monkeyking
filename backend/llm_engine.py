"""Multi-provider LLM engine — routes calls to user's configured provider."""
import os
import httpx
import asyncio

SYSTEM_DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

# Provider configs: base_url, default model, auth header format
PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "max_tokens": 8192,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "max_tokens": 4096,
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "is_anthropic": True,
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-1.5-pro",
        "max_tokens": 4096,
        "is_google": True,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 4096,
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-large-latest",
        "max_tokens": 4096,
    },
    "ollama": {
        "base_url": OLLAMA_BASE_URL,
        "model": OLLAMA_MODEL,
        "max_tokens": 4096,
        "is_ollama": True,
    },
}


def get_user_llm_config(db, user_id: int) -> tuple[str, str]:
    """Get the active provider and API key for a user. Falls back to system DeepSeek."""
    from models import UserLLMSettings
    settings = db.query(UserLLMSettings).filter_by(user_id=user_id).first()

    if settings and settings.active_provider:
        provider = settings.active_provider
        key_map = {
            "deepseek": settings.deepseek_key,
            "openai": settings.openai_key,
            "anthropic": settings.anthropic_key,
            "google": settings.google_key,
            "groq": settings.groq_key,
            "mistral": settings.mistral_key,
        }
        api_key = key_map.get(provider)
        if api_key:
            return provider, api_key

    # Fallback to system DeepSeek key
    return "deepseek", SYSTEM_DEEPSEEK_KEY


async def _call_openai_compatible(base_url: str, api_key: str, model: str,
                                   messages: list, temperature: float, max_tokens: int) -> str:
    """Call OpenAI-compatible API (works for OpenAI, DeepSeek, Groq, Mistral)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
    return ""


async def _call_anthropic(api_key: str, model: str, messages: list,
                           temperature: float, max_tokens: int) -> str:
    """Call Anthropic Claude API."""
    system_msg = ""
    user_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            user_messages.append(m)

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": user_messages,
    }
    if system_msg:
        body["system"] = system_msg

    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
    return ""


async def _call_google(api_key: str, model: str, messages: list,
                        temperature: float, max_tokens: int) -> str:
    """Call Google Gemini API."""
    contents = []
    system_instruction = None
    for m in messages:
        if m["role"] == "system":
            system_instruction = m["content"]
        else:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})

    body = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
    return ""


async def _call_ollama(model: str, messages: list, temperature: float, max_tokens: int) -> str:
    """Call local Ollama API."""
    # Build prompt from messages
    prompt_parts = []
    for m in messages:
        if m["role"] == "system":
            prompt_parts.append(f"System: {m['content']}")
        else:
            prompt_parts.append(m["content"])
    prompt = "\n\n".join(prompt_parts)

    async with httpx.AsyncClient(timeout=300.0) as client:
        for attempt in range(2):
            try:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False,
                           "options": {"temperature": temperature, "num_predict": max_tokens}},
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
            except Exception:
                if attempt == 1:
                    raise
                await asyncio.sleep(2)
    return ""


async def call_llm(provider: str, api_key: str, prompt: str,
                    system: str = "", temperature: float = 0.2) -> str:
    """Universal LLM call — routes to the correct provider."""
    config = PROVIDERS.get(provider, PROVIDERS["deepseek"])
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    if config.get("is_ollama"):
        return await _call_ollama(config["model"], messages, temperature, config["max_tokens"])
    elif config.get("is_anthropic"):
        return await _call_anthropic(api_key, config["model"], messages, temperature, config["max_tokens"])
    elif config.get("is_google"):
        return await _call_google(api_key, config["model"], messages, temperature, config["max_tokens"])
    else:
        # OpenAI-compatible: DeepSeek, OpenAI, Groq, Mistral
        return await _call_openai_compatible(
            config["base_url"], api_key, config["model"],
            messages, temperature, config["max_tokens"],
        )
