"""OpenAI-compatible chat completion provider adapter."""
import asyncio
import json
import logging
import re
from typing import Optional, Type, TypeVar
from openai import AsyncOpenAI, APIError, APITimeoutError
from pydantic import BaseModel

from app.llm.base import BaseChatAdapter

logger = logging.getLogger("hiring_eval_lab.llm")
T = TypeVar("T", bound=BaseModel)

class OpenAICompatibleAdapter(BaseChatAdapter):
    """Adapter for OpenAI and OpenAI-compatible REST API endpoints."""

    def __init__(
        self,
        model_id: str,
        api_key: str,
        base_url: Optional[str] = None,
        provider_name: str = "openai_compatible",
        timeout_seconds: int = 60
    ):
        super().__init__(model_id=model_id, provider_name=provider_name, timeout_seconds=timeout_seconds)
        self.client = AsyncOpenAI(
            api_key=api_key or "not-set",
            base_url=base_url or "https://api.openai.com/v1",
            timeout=float(timeout_seconds)
        )

    def _sanitize_error(self, err: Exception) -> str:
        """Sanitizes error string to remove potential secrets or raw bearer tokens."""
        err_msg = str(err)
        # Redact bearer tokens or api keys if present
        err_msg = re.sub(r"Bearer\s+[a-zA-Z0-9_\-\.]+", "Bearer [REDACTED]", err_msg, flags=re.IGNORECASE)
        err_msg = re.sub(r"sk-[a-zA-Z0-9_\-\.]{15,}", "[REDACTED_API_KEY]", err_msg)
        return err_msg

    def _extract_json(self, raw_content: str) -> dict:
        """Extracts a JSON object from model text: strips think-blocks and fences, tolerates raw newlines."""
        cleaned = re.sub(r"<think>.*?</think>", "", raw_content or "", flags=re.DOTALL | re.IGNORECASE).strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            return json.loads(cleaned, strict=False)
        except json.JSONDecodeError:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start == -1 or end <= start:
                raise
            return json.loads(cleaned[start:end + 1], strict=False)

    @staticmethod
    def _failed_generation(err: Exception) -> str:
        """Returns the provider's rejected output (Groq 'failed_generation') if present."""
        body = getattr(err, "body", None)
        if isinstance(body, dict):
            inner = body.get("error", body)
            if isinstance(inner, dict):
                return str(inner.get("failed_generation") or "")
        return ""

    async def _complete(self, system_prompt: str, prompt: str, json_mode: bool) -> str:
        is_reasoning = any(prefix in self.model_id.lower() for prefix in ("gpt-6", "gpt-5", "o1", "o3"))
        kwargs = dict(
            model=self.model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )
        if is_reasoning:
            kwargs["max_completion_tokens"] = 6000
        else:
            kwargs["temperature"] = 0.1
            kwargs["max_tokens"] = 6000

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            response = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            retry = False
            if "max_completion_tokens" in err_str and "max_tokens" in kwargs:
                kwargs.pop("max_tokens", None)
                kwargs["max_completion_tokens"] = 6000
                retry = True
            if "temperature" in err_str and "temperature" in kwargs:
                kwargs.pop("temperature", None)
                retry = True
            if retry:
                response = await self.client.chat.completions.create(**kwargs)
            else:
                raise
        return response.choices[0].message.content or ""

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str,
        response_model: Type[T]
    ) -> T:
        """Generates structured response validated against response_model."""
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        enriched_system_prompt = (
            f"{system_prompt}\n\n"
            f"IMPORTANT: You must output ONLY a valid JSON object strictly complying with this JSON Schema:\n"
            f"{schema_json}\n"
            f"Do not include any prose, explanations, or markdown fences outside the JSON object."
        )

        compact = (
            enriched_system_prompt
            + "\n\nKeep every text field concise (under 250 words), use \\n for line breaks inside strings, "
              "and escape any double quotes inside strings."
        )
        attempts = [
            (enriched_system_prompt, True), (compact, False), (compact, True),
            (compact, False), (compact, True),
        ]
        last_error: Exception = RuntimeError("no attempt made")
        user_prompt = prompt
        try:
            for system_text, json_mode in attempts:
                try:
                    raw_text = await self._complete(system_text, user_prompt, json_mode)
                except APIError as err:
                    salvage = self._failed_generation(err)
                    if getattr(err, "status_code", None) == 429:
                        last_error = err  # rate limited: wait as the provider suggests, then retry
                        hint = re.search(r"try again in ([\d.]+)\s*(ms|s)", str(err))
                        wait = float(hint.group(1)) / (1000 if hint and hint.group(2) == "ms" else 1) if hint else 3.0
                        await asyncio.sleep(min(wait + 0.5, 20.0))
                        continue
                    if not salvage:
                        if getattr(err, "status_code", None) == 400:
                            last_error = err
                            continue  # provider rejected JSON mode: retry as plain text
                        raise
                    raw_text = salvage
                try:
                    return response_model.model_validate(self._extract_json(raw_text))
                except Exception as parse_err:  # malformed JSON or schema mismatch: retry compactly
                    last_error = parse_err
                    logger.warning(f"{self.model_id} reply not usable ({parse_err}): {raw_text[:200]!r}")
                    if raw_text.strip() and (isinstance(parse_err, json.JSONDecodeError) or "{" not in raw_text):
                        # The model answered in prose: ask it to restate that answer as the JSON object.
                        user_prompt = (
                            f"{prompt}\n\nYour previous reply was plain text, not JSON:\n"
                            f"{raw_text.strip()[:3000]}\n\n"
                            "Restate that answer as the required JSON object only. Even if the case is weak, "
                            "give the best honest argument with a low confidence score and quote evidence "
                            "values exactly from the inputs."
                        )
            raise last_error
        except (APIError, APITimeoutError) as err:
            sanitized = self._sanitize_error(err)
            logger.error(f"Provider API error for model {self.model_id}: {sanitized}")
            raise RuntimeError(f"Model provider error ({self.provider_name}): {sanitized}") from err
        except Exception as err:
            sanitized = self._sanitize_error(err)
            logger.error(f"Failed to generate structured output from {self.model_id}: {sanitized}")
            raise RuntimeError(f"Structured output error ({self.provider_name}): {sanitized}") from err

