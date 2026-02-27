"""Rule-based ontology expansion for Phase B-2.

This module adds deterministic extraction for:
- UseCase (Annex III high-risk application areas)
- ComplianceReq (Article 9~15 shall/must requirements)
- Timeline (date-driven enforcement milestones)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
)
DATE_PATTERNS = [
    re.compile(rf"\b(\d{{1,2}}\s+(?:{MONTH_PATTERN})\s+\d{{4}})\b", re.IGNORECASE),
    re.compile(rf"\b((?:{MONTH_PATTERN})\s+\d{{4}})\b", re.IGNORECASE),
    re.compile(r"\b(\d{4}\.\d{2})\b"),
]
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
SHALL_PATTERN = re.compile(r"\b(shall|must)\b", re.IGNORECASE)
ARTICLE_PATTERN = re.compile(r"^Article\s+(\d+)\b", re.IGNORECASE)

USECASE_RULES: List[Dict[str, Any]] = [
    {
        "id": "UC-01",
        "title": "Biometric identification and categorisation",
        "annex_point": "Annex III.1",
        "keywords": [
            "biometric",
            "remote biometric",
            "emotion recognition",
            "biometric categorisation",
        ],
    },
    {
        "id": "UC-02",
        "title": "Critical infrastructure operations",
        "annex_point": "Annex III.2",
        "keywords": [
            "critical infrastructure",
            "road traffic",
            "water",
            "gas",
            "electricity",
        ],
    },
    {
        "id": "UC-03",
        "title": "Education and vocational training",
        "annex_point": "Annex III.3",
        "keywords": [
            "education",
            "vocational training",
            "student",
            "admission",
        ],
    },
    {
        "id": "UC-04",
        "title": "Employment and workers management",
        "annex_point": "Annex III.4",
        "keywords": [
            "employment",
            "recruitment",
            "workers",
            "promotion",
            "termination",
        ],
    },
    {
        "id": "UC-05",
        "title": "Essential private/public services",
        "annex_point": "Annex III.5",
        "keywords": [
            "essential services",
            "credit score",
            "creditworthiness",
            "public assistance",
            "benefits",
        ],
    },
    {
        "id": "UC-06",
        "title": "Law enforcement",
        "annex_point": "Annex III.6",
        "keywords": [
            "law enforcement",
            "criminal offence",
            "investigate",
            "prosecute",
            "police",
        ],
    },
    {
        "id": "UC-07",
        "title": "Migration, asylum, border control",
        "annex_point": "Annex III.7",
        "keywords": [
            "migration",
            "asylum",
            "border control",
            "visa",
        ],
    },
    {
        "id": "UC-08",
        "title": "Administration of justice and democratic processes",
        "annex_point": "Annex III.8",
        "keywords": [
            "administration of justice",
            "democratic process",
            "judicial authority",
            "court",
        ],
    },
]

ACTOR_HINTS = [
    "Provider",
    "Deployer",
    "Importer",
    "Distributor",
    "Authorised Representative",
    "Notified Body",
]


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _slug(text: str, limit: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:limit] if slug else "n-a"


def _extract_article_num_from_header(header: str) -> Optional[int]:
    match = ARTICLE_PATTERN.match(header or "")
    if not match:
        return None
    return int(match.group(1))


def _iter_sentences(text: str) -> Iterable[str]:
    normalized = _normalize_space(text)
    if not normalized:
        return []
    return [s.strip() for s in SENTENCE_SPLIT.split(normalized) if s.strip()]


def extract_use_cases(chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract 8 Annex III use-cases with deterministic keyword rules."""
    use_cases: List[Dict[str, Any]] = []
    full_text = " ".join(_normalize_space(str(c.get("content", ""))) for c in chunks).lower()

    for rule in USECASE_RULES:
        evidence_headers: Set[str] = set()
        evidence_articles: Set[str] = set()
        keyword_hits = 0

        for kw in rule["keywords"]:
            if kw.lower() in full_text:
                keyword_hits += 1

        for chunk in chunks:
            content = _normalize_space(str(chunk.get("content", ""))).lower()
            if not content:
                continue
            if any(kw.lower() in content for kw in rule["keywords"]):
                header = str(chunk.get("header", "")).strip()
                if header:
                    evidence_headers.add(header)
                article_num = chunk.get("article_num", 0)
                if article_num:
                    evidence_articles.add(f"Article {int(article_num)}")

        use_cases.append(
            {
                "id": rule["id"],
                "title": rule["title"],
                "annex_point": rule["annex_point"],
                "keywords": rule["keywords"],
                "keyword_hit_count": keyword_hits,
                "evidence_headers": sorted(evidence_headers),
                "evidence_articles": sorted(evidence_articles),
            }
        )

    logger.info("B-2 UseCase 추출 완료: %d개", len(use_cases))
    return use_cases


def extract_compliance_requirements(
    chunks: Sequence[Dict[str, Any]],
    article_min: int = 9,
    article_max: int = 15,
) -> List[Dict[str, Any]]:
    """Extract Article 9~15 requirements with shall/must patterns."""
    requirements: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, int]] = set()

    for chunk in chunks:
        article_num = int(chunk.get("article_num", 0) or 0)
        if article_num < article_min or article_num > article_max:
            continue

        header = str(chunk.get("header", "")).strip()
        content = str(chunk.get("content", ""))
        for sentence in _iter_sentences(content):
            if not SHALL_PATTERN.search(sentence):
                continue
            normalized_sentence = _normalize_space(sentence)
            dedupe_key = (normalized_sentence.lower(), article_num)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            actor = ""
            for hint in ACTOR_HINTS:
                if re.search(rf"\b{re.escape(hint)}s?\b", sentence, re.IGNORECASE):
                    actor = hint
                    break

            req_id = f"CR-A{article_num}-{len(requirements)+1:03d}-{_slug(normalized_sentence, 30)}"
            requirements.append(
                {
                    "id": req_id,
                    "text": normalized_sentence,
                    "article_num": article_num,
                    "article_id": f"Article {article_num}",
                    "source_header": header,
                    "modality": "shall" if re.search(r"\bshall\b", sentence, re.IGNORECASE) else "must",
                    "actor_hint": actor,
                }
            )

    logger.info("B-2 ComplianceReq 추출 완료: %d개", len(requirements))
    return requirements


def extract_timelines(chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract timeline milestones from date-like expressions."""
    timelines: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, int, str]] = set()

    for chunk in chunks:
        article_num = int(chunk.get("article_num", 0) or 0)
        header = str(chunk.get("header", "")).strip()
        content = str(chunk.get("content", ""))
        sentences = list(_iter_sentences(content))

        for sentence in sentences:
            matches: List[str] = []
            for pattern in DATE_PATTERNS:
                matches.extend([m.group(1) for m in pattern.finditer(sentence)])
            if not matches:
                continue
            for date_text in matches:
                normalized_date = _normalize_space(date_text)
                event_text = _normalize_space(sentence)
                key = (normalized_date.lower(), article_num, event_text.lower())
                if key in seen:
                    continue
                seen.add(key)
                timeline_id = (
                    f"TL-{article_num or 0}-{len(timelines)+1:03d}-{_slug(normalized_date, 20)}"
                )
                timelines.append(
                    {
                        "id": timeline_id,
                        "date_text": normalized_date,
                        "event_text": event_text,
                        "article_num": article_num,
                        "article_id": f"Article {article_num}" if article_num else "",
                        "source_header": header,
                    }
                )

    logger.info("B-2 Timeline 추출 완료: %d개", len(timelines))
    return timelines


def extract_schema_entities(chunks: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Run B-2 deterministic extraction for all schema entities."""
    use_cases = extract_use_cases(chunks)
    compliance_reqs = extract_compliance_requirements(chunks)
    timelines = extract_timelines(chunks)
    return {
        "use_cases": use_cases,
        "compliance_reqs": compliance_reqs,
        "timelines": timelines,
    }


def save_schema_entities(
    schema_data: Dict[str, List[Dict[str, Any]]],
    output_path: Path,
) -> None:
    """Save B-2 schema extraction outputs as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema_data, f, ensure_ascii=False, indent=2)
    logger.info("B-2 산출물 저장 완료: %s", output_path)


def load_schema_entities_to_neo4j(
    schema_data: Dict[str, List[Dict[str, Any]]],
    graph: Any,
) -> Dict[str, int]:
    """Load UseCase/ComplianceReq/Timeline nodes and links into Neo4j."""
    counts = {"use_cases": 0, "compliance_reqs": 0, "timelines": 0}

    for item in schema_data.get("use_cases", []):
        cypher = """
        MERGE (u:UseCase {id: $id})
        SET u.title = $title,
            u.annex_point = $annex_point,
            u.keyword_hit_count = $keyword_hit_count
        WITH u
        MERGE (r:Riskcategory {id: 'High-Risk'})
        MERGE (u)-[:CLASSIFIED_AS]->(r)
        """
        graph.query(
            cypher,
            params={
                "id": item["id"],
                "title": item["title"],
                "annex_point": item["annex_point"],
                "keyword_hit_count": int(item.get("keyword_hit_count", 0)),
            },
        )
        for article_id in item.get("evidence_articles", []):
            link_cypher = """
            MATCH (u:UseCase {id: $usecase_id})
            MERGE (a:Article {id: $article_id})
            MERGE (u)-[:REFERENCES]->(a)
            """
            graph.query(
                link_cypher,
                params={"usecase_id": item["id"], "article_id": article_id},
            )
        counts["use_cases"] += 1

    for item in schema_data.get("compliance_reqs", []):
        cypher = """
        MERGE (c:ComplianceReq {id: $id})
        SET c.text = $text,
            c.modality = $modality,
            c.source_header = $source_header,
            c.article_num = $article_num
        WITH c
        MERGE (a:Article {id: $article_id})
        MERGE (c)-[:DEFINED_IN]->(a)
        """
        graph.query(
            cypher,
            params={
                "id": item["id"],
                "text": item["text"],
                "modality": item["modality"],
                "source_header": item["source_header"],
                "article_num": int(item["article_num"]),
                "article_id": item["article_id"],
            },
        )
        actor_hint = item.get("actor_hint", "").strip()
        if actor_hint:
            actor_cypher = """
            MATCH (c:ComplianceReq {id: $req_id})
            MERGE (a:Actor {id: $actor_id})
            MERGE (c)-[:APPLIES_TO]->(a)
            """
            graph.query(
                actor_cypher,
                params={"req_id": item["id"], "actor_id": actor_hint},
            )
        counts["compliance_reqs"] += 1

    for item in schema_data.get("timelines", []):
        cypher = """
        MERGE (t:Timeline {id: $id})
        SET t.date_text = $date_text,
            t.event_text = $event_text,
            t.source_header = $source_header,
            t.article_num = $article_num
        """
        graph.query(
            cypher,
            params={
                "id": item["id"],
                "date_text": item["date_text"],
                "event_text": item["event_text"],
                "source_header": item["source_header"],
                "article_num": int(item.get("article_num", 0)),
            },
        )
        article_id = item.get("article_id", "").strip()
        if article_id:
            link_cypher = """
            MATCH (t:Timeline {id: $timeline_id})
            MERGE (a:Article {id: $article_id})
            MERGE (t)-[:IMPLEMENTS]->(a)
            """
            graph.query(
                link_cypher,
                params={"timeline_id": item["id"], "article_id": article_id},
            )
        counts["timelines"] += 1

    logger.info(
        "B-2 Neo4j 적재 완료: UseCase=%d, ComplianceReq=%d, Timeline=%d",
        counts["use_cases"],
        counts["compliance_reqs"],
        counts["timelines"],
    )
    return counts

