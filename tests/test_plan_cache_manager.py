from apc.llm.base import LLMProvider, LLMResponse

from octotools.plan_cache.manager import PlanCacheManager


class ChangingKeywordLLM(LLMProvider):
    """Return different synonyms on consecutive calls."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "changing-keyword-test-model"

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        responses = [
            "simple addition",
            "basic addition",
        ]

        content = responses[
            min(self.calls, len(responses) - 1)
        ]
        self.calls += 1

        return LLMResponse(
            content=content,
            model=self.model_name,
            raw=content,
        )


def test_identical_query_reuses_first_keyword(tmp_path):
    llm = ChangingKeywordLLM()

    manager = PlanCacheManager(
        llm,
        cache_path=tmp_path / "plan-cache.json",
        max_size=16,
    )

    first = manager.lookup(
        "What is 12 plus 12?",
        ["Generalist_Solution_Generator_Tool"],
        has_image=False,
    )

    second = manager.lookup(
        "what   is 12 plus 12?",
        ["Generalist_Solution_Generator_Tool"],
        has_image=False,
    )

    assert first.keyword == "simple addition"
    assert second.keyword == first.keyword
    assert second.cache_key == first.cache_key

    # The second lookup must not call the LLM again.
    assert llm.calls == 1
