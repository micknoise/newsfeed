"""Wrapper for the local LLM (OpenAI-compatible API at localhost:1234/v1)."""

import os
from pathlib import Path

import yaml
from openai import OpenAI

_config_path = Path(__file__).parent.parent / "config.yaml"


def _cfg() -> dict:
    with open(_config_path) as f:
        return yaml.safe_load(f)["llm"]


def _client() -> OpenAI:
    cfg = _cfg()
    base_url = os.environ.get("LLM_BASE_URL", cfg["base_url"])
    return OpenAI(base_url=base_url, api_key="lm-studio")


def complete(
    prompt: str,
    system: str = "You are a helpful assistant.",
    max_tokens: int = 400,
    temperature: float | None = None,
) -> str:
    """Single-turn completion via the local LLM. Returns the response text."""
    cfg = _cfg()
    model = os.environ.get("LLM_MODEL", cfg["model"])
    temp = temperature if temperature is not None else cfg.get("temperature", 0.3)
    client = _client()
    resp = client.chat.completions.create(
        model=model,
        temperature=temp,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content.strip()
