"""Lightweight lexical RAG over RTLerror-analysis knowledge_base examples."""

from __future__ import annotations

import os
import re
from pathlib import Path

from octotools.tools.base import BaseTool


class VerilogRagTool(BaseTool):
    """Retrieve correction examples without adding a plan cache."""

    def __init__(self):
        super().__init__(
            tool_name="VerilogRagTool",
            tool_description=(
                "Retrieve similar RTLerror-analysis correction examples for a failed "
                "candidate; results are fed to the repair prompt and Memory."
            ),
            tool_version="1.0.0",
            input_types={
                "specification": "str, required",
                "candidate_code": "str",
                "error_category": "str",
                "top_k": "int",
                "knowledge_base": "str",
            },
            output_type="dict containing ranked RTL examples and retrieval scores",
            demo_commands=[],
        )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower()))

    def execute(
        self,
        specification: str,
        candidate_code: str = "",
        error_category: str = "unclassified",
        top_k: int = 3,
        knowledge_base: str | None = None,
    ):
        root = Path(knowledge_base or os.environ.get(
            "OCTOVERILOG_RAG_KB",
            "/home/htt/projects/RTLerrorAnalysis/error_correction/code_rag/knowledge_base",
        ))
        if not root.is_dir():
            return {"success": False, "examples": [], "error": f"knowledge base not found: {root}"}
        query = self._tokens(f"{specification} {candidate_code} {error_category}")
        scored = []
        for path in root.glob("*"):
            if not path.is_file() or path.suffix.lower() not in {".txt", ".sv"}:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            tokens = self._tokens(content)
            overlap = len(query & tokens)
            score = overlap / max(1, len(query))
            if overlap:
                scored.append((score, overlap, path.name, content))
        scored.sort(key=lambda item: (-item[0], -item[1], item[2].lower()))
        examples = [
            {"name": name, "score": round(score, 6), "content": content[:6000]}
            for score, _, name, content in scored[: max(1, int(top_k))]
        ]
        context = "\n\n".join(
            f"[Retrieved example: {item['name']} score={item['score']}]\n{item['content']}"
            for item in examples
        )
        return {
            "success": True,
            "query_terms": sorted(query),
            "examples": examples,
            "context": context,
            "knowledge_base": str(root),
        }
