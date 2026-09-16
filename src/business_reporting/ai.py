from __future__ import annotations

import json
import os
import urllib.request


def generate_executive_summary(metrics: dict[str, object]) -> str:
    """Stage 2 narrates the locked KPI payload; it does not calculate financial values."""
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("Set LLM_API_KEY before requesting an AI summary")
    base_url = os.environ.get("LLM_API_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4.1-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Write a concise three-bullet executive summary. Use only supplied metrics. Never recalculate or invent values."},
            {"role": "user", "content": json.dumps(metrics, sort_keys=True)},
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions", data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return str(json.load(response)["choices"][0]["message"]["content"])
