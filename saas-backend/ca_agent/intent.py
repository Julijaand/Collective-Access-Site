"""
CA Agent - Intent Parsing via OpenAI-compatible API (OpenRouter)

Required env vars (set in k8s/ca-agent-deployment.yaml):
  LLM_BASE_URL  — provider base URL, e.g. https://openrouter.ai/api/v1
  LLM_API_KEY   — provider API key
  LLM_MODEL     — model ID, set via LLM_MODEL env var
"""
import json
import logging
import os
import re
import httpx
from .prompts import INTENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")

VALID_ACTIONS = {"search", "create", "edit", "get", "delete", "unknown"}
VALID_ENTITIES = {"object", "entity", "occurrence", "collection"}


async def parse_intent(message: str, api_key: str, model: str) -> dict:
    """
    Send message to OpenAI-compatible API and parse the structured intent JSON.
    Returns dict with keys: action, entity, params
    """
    base_url = LLM_BASE_URL
    if not api_key:
        logger.error("LLM_API_KEY is not set. Check K8s secrets.")
        return _unknown_intent(message)
    if not model:
        logger.error("LLM_MODEL is not set. Check K8s env vars.")
        return _unknown_intent(message)

    prompt = INTENT_SYSTEM_PROMPT + f'\nUser: "{message}"\nResponse:'

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://collective-museum.com",
        "X-Title": "CA Agent",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 256,
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            raw_text = resp.json()["choices"][0]["message"]["content"]
            logger.info("Intent parsed via %s / %s", base_url, model)
            return _extract_json(raw_text)
    except httpx.TimeoutException:
        logger.error("LLM timeout parsing intent (%s)", base_url)
        return _unknown_intent(message)
    except Exception as e:
        logger.error("Intent parsing error (%s): %s", base_url, e)
        return _unknown_intent(message)


def _extract_json(text: str) -> dict:
    """Extract and validate JSON from LLM response text."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Greedy match — from first { to last } to handle nested objects
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        logger.warning("No JSON found in LLM response: %s", text)
        return _unknown_intent(text)

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error: %s — raw: %s", e, text)
        return _unknown_intent(text)

    action = data.get("action", "unknown")
    entity = data.get("entity", "object")
    params = data.get("params", {})

    # Validate
    if action not in VALID_ACTIONS:
        action = "unknown"
    if entity not in VALID_ENTITIES:
        entity = "object"
    if not isinstance(params, dict):
        params = {}

    return {"action": action, "entity": entity, "params": params}


def _unknown_intent(original: str) -> dict:
    return {
        "action": "unknown",
        "entity": "object",
        "params": {"original_message": original},
    }
