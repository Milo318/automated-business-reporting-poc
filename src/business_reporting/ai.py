from __future__ import annotations

import json
import os
from .transport import request_object
from .autonomy import verified_summary


def propose_analysis(change: dict[str, object]) -> dict[str, object]:
    """Narrate a deterministically selected change; policy code verifies every claim."""
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("Set LLM_API_KEY before requesting an AI summary")
    base_url = os.environ.get("LLM_API_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4.1-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "Return JSON with metric, direction, previous, current, summary, and statement_type. Copy all numeric claims exactly from the supplied verified change and copy required_summary verbatim as summary. Set statement_type to verified_fact.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {**change, "required_summary": verified_summary(change)},
                    sort_keys=True,
                ),
            },
        ],
    }
    result = request_object(payload, base_url, api_key)
    if not isinstance(result, dict):
        raise ValueError("AI analysis must be a JSON object")
    return result
