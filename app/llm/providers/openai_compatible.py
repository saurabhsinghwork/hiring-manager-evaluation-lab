"""OpenAI-compatible chat completion provider adapter."""
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
        kwargs = dict(
            model=self.model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=6000,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await self.client.chat.completions.create(**kwargs)
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
        attempts = [(enriched_system_prompt, True), (compact, False), (compact, False)]
        last_error: Exception = RuntimeError("no attempt made")
        try:
            for system_text, json_mode in attempts:
                try:
                    raw_text = await self._complete(system_text, prompt, json_mode)
                except APIError as err:
                    salvage = self._failed_generation(err)
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
            raise last_error
        except (APIError, APITimeoutError) as err:
            sanitized = self._sanitize_error(err)
            logger.error(f"Provider API error for model {self.model_id}: {sanitized}")
            raise RuntimeError(f"Model provider error ({self.provider_name}): {sanitized}") from err
        except Exception as err:
            sanitized = self._sanitize_error(err)
            logger.error(f"Failed to generate structured output from {self.model_id}: {sanitized}")
            raise RuntimeError(f"Structured output error ({self.provider_name}): {sanitized}") from err

