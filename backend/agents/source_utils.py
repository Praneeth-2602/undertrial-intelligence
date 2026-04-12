from __future__ import annotations

from hashlib import sha1
from typing import Iterable

from langchain.schema import Document

from agents.state import SourceRecord


def _normalize_excerpt(text: str, limit: int = 320) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _source_key(source: SourceRecord) -> str:
    base = "|".join(
        [
            source.get("document_id", ""),
            source.get("title", ""),
            source.get("source", ""),
            source.get("excerpt", ""),
        ]
    )
    return sha1(base.encode("utf-8")).hexdigest()


def documents_to_context_and_sources(
    docs: list[Document], used_by: str
) -> tuple[str, list[SourceRecord]]:
    context_parts: list[str] = []
    sources: list[SourceRecord] = []

    for doc in docs:
        metadata = doc.metadata or {}
        title = str(metadata.get("title") or metadata.get("case_id") or "Untitled source")
        excerpt = _normalize_excerpt(doc.page_content)
        source_record: SourceRecord = {
            "title": title,
            "excerpt": excerpt,
            "source": str(metadata.get("source") or metadata.get("docsource") or "unknown"),
            "category": str(metadata.get("category") or "unknown"),
            "court": str(metadata.get("court") or metadata.get("docsource") or ""),
            "document_id": str(metadata.get("document_id") or metadata.get("case_id") or ""),
            "used_by": [used_by],  # type: ignore[list-item]
        }
        sources.append(source_record)
        context_parts.append(
            "\n".join(
                [
                    f"Title: {source_record['title']}",
                    f"Source: {source_record['source']}",
                    f"Category: {source_record['category']}",
                    f"Court: {source_record['court'] or 'Not specified'}",
                    f"Document ID: {source_record['document_id'] or 'Not specified'}",
                    f"Excerpt: {excerpt}",
                ]
            )
        )

    return "\n\n---\n\n".join(context_parts), sources


def merge_sources(*source_groups: Iterable[SourceRecord]) -> list[SourceRecord]:
    merged: dict[str, SourceRecord] = {}

    for group in source_groups:
        for source in group:
            key = _source_key(source)
            if key not in merged:
                merged[key] = {
                    **source,
                    "used_by": list(source.get("used_by", [])),
                }
                continue

            existing = merged[key]
            labels = set(existing.get("used_by", []))
            labels.update(source.get("used_by", []))
            existing["used_by"] = sorted(labels)  # type: ignore[assignment]

            if not existing.get("court") and source.get("court"):
                existing["court"] = source["court"]
            if not existing.get("document_id") and source.get("document_id"):
                existing["document_id"] = source["document_id"]

    return list(merged.values())


def format_sources_for_prompt(sources: list[SourceRecord], limit: int = 10) -> str:
    prompt_parts: list[str] = []
    for source in sources[:limit]:
        prompt_parts.append(
            "\n".join(
                [
                    f"Title: {source['title']}",
                    f"Source: {source['source']}",
                    f"Used by: {', '.join(source['used_by'])}",
                    f"Excerpt: {source['excerpt']}",
                ]
            )
        )
    return "\n\n---\n\n".join(prompt_parts)
