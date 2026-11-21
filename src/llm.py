"""Wrapper for local LLMs, each served as an OpenAI-compatible API."""

import os
import re
from pathlib import Path

import requests
import yaml
from openai import OpenAI

_config_path = Path(__file__).parent.parent / "config.yaml"


def _cfg() -> dict:
    with open(_config_path) as f:
        return yaml.safe_load(f)["llm"]


def _client(base_url: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key="not-needed", timeout=120)


def _complete_no_think(
    base_url: str, model: str, system: str, prompt: str, max_tokens: int, temp: float
) -> str:
    """Ollama's native /api/chat, with think:false honoured.

    Hybrid-reasoning models (e.g. qwen3.8) spend max_tokens on hidden
    reasoning first via the OpenAI-compatible /v1 endpoint, which ignores
    think=false and can leave nothing for the visible answer. Ollama's own
    /api/chat respects it.
    """
    resp = requests.post(
        base_url.removesuffix("/v1") + "/api/chat",
        json={
            "model": model,
            "think": False,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temp},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def complete(
    prompt: str,
    system: str = "You are a helpful assistant.",
    max_tokens: int = 400,
    temperature: float | None = None,
    base_url: str | None = None,
    model: str | None = None,
    think: bool = True,
    reasoning_effort: str | None = None,
    ttl: int | None = None,
) -> str:
    """Single-turn completion via a local LLM. Returns the response text.

    `base_url`/`model` default to the top-level `llm:` config, overridable
    via LLM_BASE_URL/LLM_MODEL env vars. Pass them explicitly (e.g. from
    `llm.digest`) to route a call to a different local model/server. Pass
    `think=False` for a hybrid-reasoning model where only the final answer
    is wanted (see `_complete_no_think`).
    """
    cfg = _cfg()
    base_url = base_url or os.environ.get("LLM_BASE_URL", cfg["base_url"])
    model = model or os.environ.get("LLM_MODEL", cfg["model"])
    temp = temperature if temperature is not None else cfg.get("temperature", 0.3)

    if not think:
        return _complete_no_think(base_url, model, system, prompt, max_tokens, temp)

    # Passed through to servers that accept them. LM Studio: `ttl` unloads
    # the model that many seconds after its last use.
    extra = {}
    if reasoning_effort:
        extra["reasoning_effort"] = reasoning_effort
    if ttl:
        extra["ttl"] = ttl
    client = _client(base_url)
    resp = client.chat.completions.create(
        model=model,
        temperature=temp,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        extra_body=extra or None,
        timeout=600,
    )
    text = resp.choices[0].message.content or ""
    # Some reasoning models leak <think>...</think> into the visible answer.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    return text.replace("<think>", "").replace("</think>", "").strip()
