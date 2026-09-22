from __future__ import annotations

import json
import os
import re
from pathlib import Path

from octotools.tools.base import BaseTool


class VerilogSearchTool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="VerilogSearchTool",
            tool_description="Search approved local JSON/JSONL benchmark roots for related RTL examples; this tool never accesses the network.",
            tool_version="1.0.0",
            input_types={"query": "str, required", "limit": "int"},
            output_type="dict containing ranked local examples",
            demo_commands=["execution = tool.execute(query='round robin arbiter', limit=3)"],
        )

    @staticmethod
    def _roots():
        configured = os.getenv("OCTOVERILOG_SEARCH_ROOTS", "/home/htt/OctoVerilog/datasets:/home/datasets/data")
        return [Path(value).resolve() for value in configured.split(":") if value]

    def execute(self, query: str, limit: int = 3):
        terms = {term.lower() for term in re.findall(r"[A-Za-z0-9_]+", query) if len(term) > 2}
        matches = []
        for root in self._roots():
            if not root.is_dir():
                continue
            for path in root.rglob("*.jsonl"):
                try:
                    with path.open(encoding="utf-8", errors="ignore") as handle:
                        for line_number, line in enumerate(handle, 1):
                            lowered = line.lower()
                            score = sum(term in lowered for term in terms)
                            if score:
                                try:
                                    row = json.loads(line)
                                    snippet = str(row.get("detail_description") or row.get("prompt") or row.get("description") or row)[:1200]
                                except Exception:
                                    snippet = line[:1200]
                                matches.append({"score": score, "path": str(path), "line": line_number, "snippet": snippet})
                except OSError:
                    continue
        matches.sort(key=lambda item: (-item["score"], item["path"], item["line"]))
        return {"success": True, "query": query, "matches": matches[: max(1, min(int(limit), 10))]}
