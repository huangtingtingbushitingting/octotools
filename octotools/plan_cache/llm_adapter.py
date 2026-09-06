import json
from typing import Any

from apc.llm.base import LLMProvider, LLMResponse

from octotools.engine.factory import create_llm_engine


class OctoToolsLLMProvider(LLMProvider):
    """Expose an OctoTools LLM engine through APC's provider interface."""

    def __init__(
        self,
        model_string: str,
        *,
        is_multimodal: bool = False,
    ) -> None:
        self._model_name = model_string
        self._engine = create_llm_engine(
            model_string=model_string,
            is_multimodal=is_multimodal,
            use_cache=False,
            usage_component="plan_cache",
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        raw: Any = self._engine(
            prompt,
            system_prompt=system or None,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if isinstance(raw, (dict, list)):
            content = json.dumps(raw, ensure_ascii=False)
        else:
            content = str(raw)

        return LLMResponse(
            content=content,
            model=self._model_name,
            raw=raw,
        )
