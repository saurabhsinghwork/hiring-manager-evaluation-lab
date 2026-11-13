"""Adapter must survive provider JSON-mode failures and messy model output."""
import asyncio
import httpx
from openai import APIStatusError

from app.llm.providers.openai_compatible import OpenAICompatibleAdapter
from app.schemas.agents import JudgeOutput

GOOD = '<think>hmm</think>```json\n{"decision":"AGAINST","winning_argument":["a","b"],"reasoning":"line1\nline2","confidence_percentage":70}\n```'


def _err(body):
    req = httpx.Request("POST", "http://x")
    return APIStatusError("bad", response=httpx.Response(400, request=req), body=body)


def _adapter(outcomes):
    adapter = OpenAICompatibleAdapter("m", "k", base_url="http://x")
    calls = []

    async def fake(system_prompt, prompt, json_mode):
        calls.append(json_mode)
        out = outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    adapter._complete = fake
    return adapter, calls


def test_salvages_failed_generation():
    adapter, calls = _adapter([_err({"error": {"failed_generation": GOOD}})])
    result = asyncio.run(adapter.generate_structured("p", "s", JudgeOutput))
    assert result.decision == "AGAINST" and calls == [True]


def test_falls_back_to_plain_text_after_400():
    adapter, calls = _adapter([_err({"error": {"message": "Failed to generate JSON"}}), GOOD])
    result = asyncio.run(adapter.generate_structured("p", "s", JudgeOutput))
    assert result.confidence_percentage == 70 and calls == [True, False]


def test_retries_on_unparseable_output():
    adapter, calls = _adapter(["not json at all", GOOD])
    assert asyncio.run(adapter.generate_structured("p", "s", JudgeOutput)).decision == "AGAINST"
