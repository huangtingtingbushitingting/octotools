import hashlib
from collections.abc import Iterable


CACHE_SCHEMA_VERSION = "v1"


def build_plan_cache_key(
    keyword: str,
    available_tools: Iterable[str],
    *,
    has_image: bool,
    schema_version: str = CACHE_SCHEMA_VERSION,
) -> str:
    normalized_keyword = " ".join(keyword.lower().split())
    normalized_tools = sorted(
        tool.strip().lower()
        for tool in available_tools
        if tool and tool.strip()
    )

    tool_fingerprint = hashlib.sha256(
        "\n".join(normalized_tools).encode("utf-8")
    ).hexdigest()[:12]

    modality = "image" if has_image else "text"

    return (
        f"{normalized_keyword}"
        f"|tools={tool_fingerprint}"
        f"|modality={modality}"
        f"|schema={schema_version}"
    )