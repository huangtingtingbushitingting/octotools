from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apc.cache.plan_cache import PlanCache
from apc.components.keyword_extractor import KeywordExtractor
from apc.components.template_extractor import TemplateExtractor
from apc.llm.base import LLMProvider
from apc.models import PlanTemplate

from octotools.plan_cache.cache_key import build_plan_cache_key
from octotools.plan_cache.template_mapper import memory_actions_to_plan


@dataclass(frozen=True)
class PlanCacheLookup:
    """Result of preparing and querying the plan cache."""

    query: str
    keyword: str
    cache_key: str
    template: PlanTemplate | None

    @property
    def hit(self) -> bool:
        return self.template is not None


class PlanCacheManager:
    """Coordinate APC keyword extraction, lookup, and template storage."""

    def __init__(
        self,
        llm: LLMProvider,
        *,
        cache_path: str | Path,
        max_size: int = 128,
    ) -> None:
        resolved_path = Path(cache_path)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        self._cache = PlanCache(
            persist_path=resolved_path,
            max_size=max_size,
        )
        self._keyword_extractor = KeywordExtractor(llm)
        self._template_extractor = TemplateExtractor(llm)

    @property
    def size(self) -> int:
        return self._cache.size

    def lookup(
        self,
        query: str,
        available_tools: Iterable[str],
        *,
        has_image: bool,
    ) -> PlanCacheLookup:
        """Extract the intent and query the context-aware plan cache."""
        tools = tuple(available_tools)
        keyword = self._keyword_extractor.extract(query)
        cache_key = build_plan_cache_key(
            keyword,
            tools,
            has_image=has_image,
        )
        template = self._cache.lookup(cache_key)

        return PlanCacheLookup(
            query=query,
            keyword=keyword,
            cache_key=cache_key,
            template=template,
        )

    def store_successful_trace(
        self,
        lookup: PlanCacheLookup,
        actions: Mapping[str, Mapping[str, Any]],
        available_tools: Iterable[str],
    ) -> PlanTemplate | None:
        """Extract and cache a template only from a fully successful trace."""
        plan = memory_actions_to_plan(lookup.query, actions)

        if not plan.steps:
            return None

        if any(step.status != "completed" for step in plan.steps):
            return None

        allowed_tools = {
            tool.strip().lower()
            for tool in available_tools
            if tool and tool.strip()
        }

        if any(
            step.tool_name.strip().lower() not in allowed_tools
            for step in plan.steps
        ):
            return None

        template = self._template_extractor.extract(plan)

        if not template.steps:
            return None

        if any(
            step.tool_name.strip().lower() not in allowed_tools
            for step in template.steps
        ):
            return None

        self._cache.store(lookup.cache_key, template)
        return template