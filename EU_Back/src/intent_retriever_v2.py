"""Precision-first intent retriever v2 for KG-grounded diagnostics."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Sequence


ARTICLE_ID_RE = re.compile(r"^article\s+(\d+)$", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9]{2,}|[\uac00-\ud7a3]{2,}", re.IGNORECASE)
GENERIC_ARTICLE_IDS = {"Article 12", "Article 13", "Article 14"}


def _normalize_article_id(value: str) -> str:
    text = str(value or "").strip()
    match = ARTICLE_ID_RE.match(text)
    if not match:
        return ""
    return f"Article {int(match.group(1))}"


def _dedupe_list(items: Sequence[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        text = str(item or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(str(text or "").lower())


def _overlap_ratio(tokens_a: Sequence[str], tokens_b: Sequence[str]) -> float:
    a = set(str(v).strip().lower() for v in tokens_a if str(v).strip())
    b = set(str(v).strip().lower() for v in tokens_b if str(v).strip())
    if not a or not b:
        return 0.0
    inter = len(a & b)
    denom = max(1, min(len(a), len(b)))
    return float(inter) / float(denom)


def _clip(text: str, max_len: int = 200) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3].rstrip() + "..."


def _normalize_article_ids(article_ids: Sequence[str]) -> List[str]:
    normalized = [_normalize_article_id(str(v)) for v in article_ids if str(v).strip()]
    return [v for v in _dedupe_list(normalized) if v]


def _safe_fulltext_query(graph: Any, *, index_name: str, query: str, limit: int) -> List[Dict[str, Any]]:
    try:
        rows = graph.query(
            """
            CALL db.index.fulltext.queryNodes($index_name, $query) YIELD node, score
            RETURN node, score
            LIMIT $limit
            """,
            {"index_name": str(index_name), "query": str(query), "limit": int(limit)},
        )
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, Mapping)]
    except Exception:
        return []
    return []


def _query_requirements_lexical(graph: Any, *, keywords: Sequence[str], limit: int = 80) -> List[Dict[str, Any]]:
    kws = [str(v).strip().lower() for v in keywords if str(v).strip()]
    if not kws:
        return []
    query_string = " OR ".join(kws[:8])
    rows: List[Mapping[str, Any]] = []
    try:
        rows = graph.query(
            """
            CALL db.index.fulltext.queryNodes('compliance_req_fulltext', $query) YIELD node, score
            MATCH (node)-[:DEFINED_IN]->(a:Article)
            RETURN coalesce(node.id,'') AS req_id,
                   coalesce(node.text,'') AS req_text,
                   a.id AS article_id,
                   score
            ORDER BY score DESC, article_id ASC
            LIMIT $limit
            """,
            {"query": str(query_string), "limit": int(limit)},
        )
    except Exception:
        rows = []
    fallback_rows = graph.query(
        """
        MATCH (c:ComplianceReq)-[:DEFINED_IN]->(a:Article)
        WITH c, a,
             reduce(score = 0, kw IN $keywords |
                score +
                CASE WHEN toLower(coalesce(c.id,'')) CONTAINS kw THEN 2 ELSE 0 END +
                CASE WHEN toLower(coalesce(c.text,'')) CONTAINS kw THEN 3 ELSE 0 END
             ) AS score
        WHERE score > 0
        RETURN c.id AS req_id,
               coalesce(c.text,'') AS req_text,
               a.id AS article_id,
               score
        ORDER BY score DESC, article_id ASC
        LIMIT $limit
        """,
        {"keywords": kws, "limit": int(limit)},
    )
    merged: Dict[str, Dict[str, Any]] = {}
    for row in list(rows or []) + list(fallback_rows or []):
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        if not article_id:
            continue
        req_id = str(row.get("req_id", "")).strip()
        req_text = str(row.get("req_text", "")).strip()
        key = f"{article_id.lower()}::{req_id.lower()}::{req_text.lower()}"
        score = float(row.get("score", 0) or 0.0)
        existing = merged.get(key)
        if existing is None or score > float(existing.get("score", 0.0)):
            merged[key] = {
                "req_id": req_id,
                "req_text": req_text,
                "article_id": article_id,
                "score": score,
            }
    rows = list(merged.values())
    out: List[Dict[str, Any]] = []
    for row in rows:
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        if not article_id:
            continue
        out.append(
            {
                "req_id": str(row.get("req_id", "")).strip(),
                "req_text": str(row.get("req_text", "")).strip(),
                "article_id": article_id,
                "base_score": float(row.get("score", 0) or 0.0),
                "source": "lexical",
            }
        )
    out.sort(key=lambda x: (-float(x.get("base_score", 0.0)), str(x.get("article_id", ""))))
    out = out[: max(1, int(limit))]
    return out


def _query_requirements_by_articles(
    graph: Any,
    *,
    article_ids: Sequence[str],
    limit_per_article: int = 4,
    limit: int = 80,
) -> List[Dict[str, Any]]:
    normalized = _normalize_article_ids(article_ids)
    if not normalized:
        return []
    rows = graph.query(
        """
        MATCH (a:Article)<-[:DEFINED_IN]-(c:ComplianceReq)
        WHERE a.id IN $article_ids
        RETURN coalesce(c.id,'') AS req_id,
               coalesce(c.text,'') AS req_text,
               a.id AS article_id
        ORDER BY a.id ASC, c.id ASC
        LIMIT $limit
        """,
        {
            "article_ids": normalized,
            "limit": int(limit),
        },
    )
    article_counts: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    for row in rows:
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        req_text = str(row.get("req_text", "")).strip()
        if not article_id or not req_text:
            continue
        if article_counts.get(article_id, 0) >= max(1, int(limit_per_article)):
            continue
        article_counts[article_id] = article_counts.get(article_id, 0) + 1
        out.append(
            {
                "req_id": str(row.get("req_id", "")).strip(),
                "req_text": req_text,
                "article_id": article_id,
                "base_score": 8.0,
                "source": "anchor_article",
            }
        )
    return out


def _query_obligations_lexical(graph: Any, *, keywords: Sequence[str], limit: int = 24) -> List[Dict[str, Any]]:
    kws = [str(v).strip().lower() for v in keywords if str(v).strip()]
    if not kws:
        return []
    query_string = " OR ".join(kws[:8])
    rows: List[Mapping[str, Any]] = []
    try:
        rows = graph.query(
            """
            CALL db.index.fulltext.queryNodes('obligation_fulltext', $query) YIELD node, score
            OPTIONAL MATCH (node)-[:DEFINED_IN]->(a:Article)
            OPTIONAL MATCH (node)-[:ENFORCED_BY]->(i:Institution)
            RETURN coalesce(node.id,'') AS obligation_id,
                   coalesce(node.description,'') AS description,
                   collect(DISTINCT a.id)[0..8] AS articles,
                   collect(DISTINCT i.id)[0..4] AS enforced_by,
                   score
            ORDER BY score DESC
            LIMIT $limit
            """,
            {"query": str(query_string), "limit": int(limit)},
        )
    except Exception:
        rows = []
    fallback_rows = graph.query(
        """
        MATCH (o:Obligation)
        WITH o,
             reduce(score = 0, kw IN $keywords |
                score +
                CASE WHEN toLower(coalesce(o.id,'')) CONTAINS kw THEN 2 ELSE 0 END +
                CASE WHEN toLower(coalesce(o.description,'')) CONTAINS kw THEN 2 ELSE 0 END
             ) AS score
        WHERE score > 0
        OPTIONAL MATCH (o)-[:DEFINED_IN]->(a:Article)
        OPTIONAL MATCH (o)-[:ENFORCED_BY]->(i:Institution)
        RETURN o.id AS obligation_id,
               coalesce(o.description,'') AS description,
               collect(DISTINCT a.id)[0..8] AS articles,
               collect(DISTINCT i.id)[0..4] AS enforced_by,
               score
        ORDER BY score DESC
        LIMIT $limit
        """,
        {"keywords": kws, "limit": int(limit)},
    )
    if fallback_rows:
        rows = list(rows or []) + list(fallback_rows)
    out: List[Dict[str, Any]] = []
    for row in rows:
        articles = [_normalize_article_id(str(v)) for v in (row.get("articles") or [])]
        articles = [v for v in _dedupe_list(articles) if v]
        out.append(
            {
                "obligation_id": str(row.get("obligation_id", "")).strip(),
                "description": str(row.get("description", "")).strip(),
                "articles": articles,
                "enforced_by": _dedupe_list([str(v).strip() for v in (row.get("enforced_by") or []) if str(v).strip()]),
                "base_score": float(row.get("score", 0) or 0.0),
                "source": "lexical",
            }
        )
    return out


def _query_articles_lexical(graph: Any, *, keywords: Sequence[str], limit: int = 20) -> List[Dict[str, Any]]:
    kws = [str(v).strip().lower() for v in keywords if str(v).strip()]
    if not kws:
        return []
    rows = graph.query(
        """
        MATCH (a:Article)
        OPTIONAL MATCH (c:ComplianceReq)-[:DEFINED_IN]->(a)
        WITH a, collect(DISTINCT toLower(coalesce(c.text,''))) AS req_texts
        WITH a,
             reduce(score = 0, kw IN $keywords |
                 score +
                 CASE WHEN toLower(coalesce(a.id,'')) = kw THEN 2 ELSE 0 END +
                 CASE WHEN ANY(v IN req_texts WHERE v CONTAINS kw) THEN 2 ELSE 0 END
             ) AS score
        WHERE score > 0
        RETURN a.id AS article_id, score
        ORDER BY score DESC, article_id ASC
        LIMIT $limit
        """,
        {"keywords": kws, "limit": int(limit)},
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        if not article_id:
            continue
        out.append({"article_id": article_id, "base_score": float(row.get("score", 0) or 0.0), "source": "lexical"})
    return out


def _query_path_support(graph: Any, *, seed_articles: Sequence[str]) -> Dict[str, float]:
    seed = [_normalize_article_id(v) for v in seed_articles]
    seed = [v for v in _dedupe_list(seed) if v]
    if not seed:
        return {}
    rows = graph.query(
        """
        MATCH (a:Article)
        WHERE a.id IN $seed_articles
        OPTIONAL MATCH (a)-[:REFERENCES]->(b:Article)
        OPTIONAL MATCH (a)-[:IMPOSES]->(p:Penalty)
        RETURN a.id AS article_id,
               collect(DISTINCT b.id)[0..20] AS references,
               count(DISTINCT p) AS penalty_count
        """,
        {"seed_articles": seed},
    )
    support: Dict[str, float] = {article_id: 1.0 for article_id in seed}
    for row in rows:
        src = _normalize_article_id(str(row.get("article_id", "")))
        if not src:
            continue
        penalty_count = int(row.get("penalty_count", 0) or 0)
        if penalty_count > 0:
            support[src] = max(support.get(src, 0.0), min(1.0, 0.8 + min(0.2, penalty_count * 0.05)))
        refs = [_normalize_article_id(str(v)) for v in (row.get("references") or [])]
        for ref in refs:
            if not ref:
                continue
            # Reference-only path evidence is weak support in precision-first mode.
            support[ref] = max(support.get(ref, 0.0), 0.20)
    return support


def _query_multihop_article_support(
    graph: Any,
    *,
    seed_articles: Sequence[str],
    max_hops: int = 2,
    limit: int = 40,
) -> Dict[str, float]:
    seeds = _normalize_article_ids(seed_articles)
    if not seeds:
        return {}
    rows = graph.query(
        """
        MATCH (s:Article)
        WHERE s.id IN $seed_articles
        OPTIONAL MATCH p=(s)-[:REFERENCES*1..2]->(a:Article)
        WITH collect(DISTINCT {article_id: a.id, hop: length(p)}) AS forward_rows, $seed_articles AS seeds
        UNWIND (forward_rows + [v IN seeds | {article_id: v, hop: 0}]) AS row
        WITH row
        WHERE row.article_id IS NOT NULL
        RETURN row.article_id AS article_id, min(row.hop) AS hop
        ORDER BY hop ASC, article_id ASC
        LIMIT $limit
        """,
        {"seed_articles": seeds, "limit": int(limit)},
    )
    support: Dict[str, float] = {}
    for row in rows:
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        if not article_id:
            continue
        hop = int(row.get("hop", 0) or 0)
        if hop <= 0:
            score = 1.0
        elif hop == 1:
            score = 0.85
        elif hop <= int(max_hops):
            score = 0.65
        else:
            continue
        support[article_id] = max(float(support.get(article_id, 0.0)), float(score))
    return support


def retrieve_issue_evidence_v2(
    *,
    graph: Any,
    theme: str,
    trigger_terms: Sequence[str],
    retrieval_keywords: Sequence[str],
    expected_control_codes: Sequence[str],
    summarize_requirement_ko: Callable[[str, str], str],
    control_code_from_label: Callable[[str], str],
    is_noisy_requirement: Callable[[str, str], bool],
    mandatory_articles: Sequence[str] = (),
    final_threshold: float = 0.58,
) -> Dict[str, Any]:
    """Retrieve and rerank issue evidence with precision-first policy."""
    normalized_theme = str(theme or "").strip()
    effective_keywords = _dedupe_list(
        [str(v).strip().lower() for v in retrieval_keywords if str(v).strip()]
        + [str(v).strip().lower() for v in trigger_terms if str(v).strip()]
    )
    focus_tokens = _tokenize(" ".join([normalized_theme] + effective_keywords))
    expected_codes = [str(v).strip() for v in expected_control_codes if str(v).strip()]
    mandatory_set = set(_normalize_article_ids(mandatory_articles))

    lexical_requirement_rows = _query_requirements_lexical(graph, keywords=effective_keywords, limit=96)
    anchor_requirement_rows = _query_requirements_by_articles(
        graph,
        article_ids=list(mandatory_set),
        limit_per_article=4,
        limit=64,
    )
    requirement_rows_merged: Dict[str, Dict[str, Any]] = {}
    for row in list(lexical_requirement_rows) + list(anchor_requirement_rows):
        req_id = str(row.get("req_id", "")).strip()
        req_text = str(row.get("req_text", "")).strip()
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        if not req_text or not article_id:
            continue
        key = f"{article_id.lower()}::{req_id.lower()}::{req_text.lower()}"
        score = float(row.get("base_score", 0.0) or 0.0)
        existing = requirement_rows_merged.get(key)
        if (
            existing is None
            or score > float(existing.get("base_score", 0.0) or 0.0)
            or (
                score == float(existing.get("base_score", 0.0) or 0.0)
                and str(row.get("source", "")) == "lexical"
            )
        ):
            requirement_rows_merged[key] = {
                "req_id": req_id,
                "req_text": req_text,
                "article_id": article_id,
                "base_score": score,
                "source": str(row.get("source", "")).strip() or "lexical",
            }
    requirement_rows = list(requirement_rows_merged.values())
    requirement_rows.sort(
        key=lambda x: (
            -float(x.get("base_score", 0.0) or 0.0),
            str(x.get("article_id", "")),
            str(x.get("req_id", "")),
        )
    )

    obligation_rows = _query_obligations_lexical(graph, keywords=effective_keywords, limit=24)
    article_rows = _query_articles_lexical(graph, keywords=effective_keywords, limit=24)
    article_lexical_map: Dict[str, float] = {}
    for row in article_rows:
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        if not article_id:
            continue
        article_lexical_map[article_id] = max(
            float(article_lexical_map.get(article_id, 0.0)),
            float(row.get("base_score", 0.0) or 0.0),
        )

    seed_articles = _dedupe_list(
        [str(v.get("article_id", "")).strip() for v in requirement_rows[:10]]
        + [str(v.get("article_id", "")).strip() for v in article_rows[:10]]
        + list(mandatory_set)
    )
    path_support = _query_path_support(graph, seed_articles=seed_articles)
    multihop_support = _query_multihop_article_support(graph, seed_articles=seed_articles, max_hops=2, limit=40)
    for article_id, score in multihop_support.items():
        path_support[article_id] = max(float(path_support.get(article_id, 0.0)), float(score))

    trace: List[Dict[str, Any]] = []
    req_candidates: List[Dict[str, Any]] = []
    aligned_pool: List[Dict[str, Any]] = []
    for row in requirement_rows:
        req_id = str(row.get("req_id", "")).strip()
        req_text = str(row.get("req_text", "")).strip()
        article_id = str(row.get("article_id", "")).strip()
        if not req_text or not article_id:
            continue
        if is_noisy_requirement(req_id, req_text):
            trace.append(
                {
                    "source": "lexical",
                    "kind": "requirement",
                    "candidate_text": _clip(req_text),
                    "article_id": article_id,
                    "base_score": float(row.get("base_score", 0.0)),
                    "final_score": 0.0,
                    "selected": False,
                    "drop_reason": "noisy_requirement",
                }
            )
            continue

        label = summarize_requirement_ko(req_text, req_id)
        code = control_code_from_label(label)
        control_alignment = 1.0 if code in expected_codes else 0.0
        token_overlap = _overlap_ratio(_tokenize(req_text + " " + req_id), focus_tokens)
        lexical_denom = 12.0 if str(row.get("source", "lexical")) == "lexical" else 10.0
        lexical_norm = min(1.0, float(row.get("base_score", 0.0)) / lexical_denom)
        path_score = float(path_support.get(article_id, 0.0))
        is_lexical_article = article_id in article_lexical_map
        if mandatory_set and article_id not in mandatory_set and not is_lexical_article:
            path_score = min(path_score, 0.30)
        elif article_id not in mandatory_set and not is_lexical_article:
            path_score = min(path_score, 0.45)
        mandatory_alignment = 1.0 if article_id in mandatory_set else 0.0
        if mandatory_set:
            base_score = (
                0.30 * lexical_norm
                + 0.20 * token_overlap
                + 0.25 * control_alignment
                + 0.15 * path_score
                + 0.10 * mandatory_alignment
            )
        else:
            base_score = (
                0.35 * lexical_norm
                + 0.25 * token_overlap
                + 0.30 * control_alignment
                + 0.10 * path_score
            )
        generic_penalty = 0.0
        if mandatory_set and article_id in GENERIC_ARTICLE_IDS and mandatory_alignment == 0.0:
            generic_penalty = 0.08 if control_alignment == 0.0 else 0.04
        final_score = max(0.0, base_score - generic_penalty)
        low_alignment_drop = (
            control_alignment == 0.0
            and mandatory_alignment == 0.0
            and (
                path_score < 0.55
                or token_overlap < 0.45
                or lexical_norm < 0.65
            )
        )
        selected = final_score >= float(final_threshold) and not low_alignment_drop
        trace.append(
            {
                "source": "control_aligned" if control_alignment > 0 else "lexical",
                "kind": "requirement",
                "candidate_text": _clip(req_text),
                "article_id": article_id,
                "base_score": float(row.get("base_score", 0.0)),
                "lexical_score_norm": round(lexical_norm, 4),
                "token_bm25_like_score": round(token_overlap, 4),
                "control_alignment_score": round(control_alignment, 4),
                "path_support_score": round(path_score, 4),
                "mandatory_alignment_score": round(mandatory_alignment, 4),
                "generic_penalty": round(generic_penalty, 4),
                "final_score": round(final_score, 4),
                "selected": bool(selected),
                "control_code": code,
            }
        )
        if selected:
            req_candidates.append(
                {
                    "req_id": req_id,
                    "req_text": req_text,
                    "article_id": article_id,
                    "score": int(round(final_score * 100)),
                    "_final_score": float(final_score),
                    "_control_alignment": float(control_alignment),
                    "_mandatory_alignment": float(mandatory_alignment),
                }
            )
        elif (control_alignment > 0.0 or mandatory_alignment > 0.0) and final_score >= 0.42:
            aligned_pool.append(
                {
                    "req_id": req_id,
                    "req_text": req_text,
                    "article_id": article_id,
                    "score": int(round(final_score * 100)),
                    "_final_score": float(final_score),
                    "_control_alignment": float(control_alignment),
                    "_mandatory_alignment": float(mandatory_alignment),
                }
            )

    req_candidates.sort(key=lambda x: (-float(x.get("_final_score", 0.0)), str(x.get("article_id", "")), str(x.get("req_id", ""))))
    selected_requirements: List[Dict[str, Any]] = []
    article_cap: Dict[str, int] = {}
    non_mandatory_req_count = 0
    for item in req_candidates:
        article_id = str(item.get("article_id", ""))
        if mandatory_set and article_id not in mandatory_set and non_mandatory_req_count >= 1:
            continue
        if article_cap.get(article_id, 0) >= 2:
            continue
        article_cap[article_id] = article_cap.get(article_id, 0) + 1
        selected_requirements.append(
            {
                "req_id": str(item.get("req_id", "")),
                "req_text": str(item.get("req_text", "")),
                "article_id": article_id,
                "score": int(item.get("score", 0) or 0),
            }
        )
        if mandatory_set and article_id not in mandatory_set:
            non_mandatory_req_count += 1
        if len(selected_requirements) >= 8:
            break

    fallback_used = False
    # Precision-first soft fallback: when strict threshold drops all requirements,
    # keep only control/anchor-aligned candidates with minimal semantic support.
    if not selected_requirements and aligned_pool:
        fallback_used = True
        aligned_pool.sort(key=lambda x: (-float(x.get("_final_score", 0.0)), str(x.get("article_id", "")), str(x.get("req_id", ""))))
        article_counts_fb: Dict[str, int] = {}
        for item in aligned_pool:
            article_id = str(item.get("article_id", ""))
            if article_counts_fb.get(article_id, 0) >= 1:
                continue
            article_counts_fb[article_id] = article_counts_fb.get(article_id, 0) + 1
            selected_requirements.append(
                {
                    "req_id": str(item.get("req_id", "")),
                    "req_text": str(item.get("req_text", "")),
                    "article_id": article_id,
                    "score": int(item.get("score", 0) or 0),
                }
            )
            if len(selected_requirements) >= 2:
                break
    if fallback_used and mandatory_set and selected_requirements:
        fb_articles = {
            str(item.get("article_id", "")).strip()
            for item in selected_requirements
            if str(item.get("article_id", "")).strip()
        }
        has_mandatory_hit = bool(fb_articles & mandatory_set)
        has_non_generic_hit = any(article not in GENERIC_ARTICLE_IDS for article in fb_articles)
        if not has_mandatory_hit and not has_non_generic_hit:
            selected_requirements = []

    selected_obligations: List[Dict[str, Any]] = []
    non_mandatory_ob_count = 0
    for row in obligation_rows[:12]:
        desc = str(row.get("description", "")).strip()
        obligation_id = str(row.get("obligation_id", "")).strip()
        if not desc and not obligation_id:
            continue
        token_overlap = _overlap_ratio(_tokenize(desc + " " + obligation_id), focus_tokens)
        lexical_norm = min(1.0, float(row.get("base_score", 0.0)) / 8.0)
        ob_articles = [str(v).strip() for v in (row.get("articles") or []) if str(v).strip()]
        path_score = max([float(path_support.get(a, 0.0)) for a in ob_articles] + [0.0])
        mandatory_alignment = 1.0 if mandatory_set and any(a in mandatory_set for a in ob_articles) else 0.0
        if mandatory_set and mandatory_alignment == 0.0 and not any(a in article_lexical_map for a in ob_articles):
            path_score = min(path_score, 0.30)
        if mandatory_set:
            final_score = (
                0.42 * lexical_norm
                + 0.28 * token_overlap
                + 0.15 * path_score
                + 0.15 * mandatory_alignment
            )
            selected = final_score >= 0.48 and (
                token_overlap >= 0.32 or path_score >= 0.60 or mandatory_alignment > 0.0
            )
            if mandatory_alignment == 0.0 and final_score < 0.62:
                selected = False
        else:
            final_score = 0.50 * lexical_norm + 0.35 * token_overlap + 0.15 * path_score
            selected = final_score >= 0.50 and (token_overlap >= 0.35 or path_score >= 0.65)
        trace.append(
            {
                "source": "lexical",
                "kind": "obligation",
                "candidate_text": _clip(desc or obligation_id),
                "article_id": ob_articles[0] if ob_articles else "",
                "base_score": float(row.get("base_score", 0.0)),
                "lexical_score_norm": round(lexical_norm, 4),
                "token_bm25_like_score": round(token_overlap, 4),
                "control_alignment_score": 0.0,
                "path_support_score": round(path_score, 4),
                "mandatory_alignment_score": round(mandatory_alignment, 4),
                "final_score": round(final_score, 4),
                "selected": bool(selected),
            }
        )
        if selected:
            if mandatory_set and mandatory_alignment == 0.0 and non_mandatory_ob_count >= 1:
                selected = False
            if not selected:
                continue
            selected_obligations.append(
                {
                    "obligation_id": obligation_id,
                    "description": desc,
                    "articles": _dedupe_list(ob_articles),
                    "enforced_by": _dedupe_list([str(v).strip() for v in (row.get("enforced_by") or []) if str(v).strip()]),
                }
            )
            if mandatory_set and mandatory_alignment == 0.0:
                non_mandatory_ob_count += 1
        if len(selected_obligations) >= 8:
            break

    selected_article_candidates: List[Dict[str, Any]] = []
    if mandatory_set:
        for article_id in sorted(mandatory_set):
            lexical_norm = min(1.0, float(article_lexical_map.get(article_id, 0.0)) / 6.0)
            path_score = float(path_support.get(article_id, 0.0))
            mandatory_alignment = 1.0
            final_score = 0.40 * mandatory_alignment + 0.35 * path_score + 0.25 * lexical_norm
            selected = final_score >= 0.45 and (path_score >= 0.45 or lexical_norm >= 0.45)
            trace.append(
                {
                    "source": "mandatory_article",
                    "kind": "article",
                    "candidate_text": f"mandatory article anchor: {article_id}",
                    "article_id": article_id,
                    "base_score": float(article_lexical_map.get(article_id, 0.0)),
                    "lexical_score_norm": round(lexical_norm, 4),
                    "token_bm25_like_score": 0.0,
                    "control_alignment_score": 0.0,
                    "path_support_score": round(path_score, 4),
                    "mandatory_alignment_score": round(mandatory_alignment, 4),
                    "final_score": round(final_score, 4),
                    "selected": bool(selected),
                }
            )
            if selected:
                selected_article_candidates.append(
                    {
                        "article_id": article_id,
                        "score": int(round(final_score * 100)),
                        "_final_score": float(final_score),
                    }
                )

    for article_id, score in list(path_support.items())[:12]:
        trace.append(
            {
                "source": "graph_path",
                "kind": "article_path",
                "candidate_text": f"graph path support: {article_id}",
                "article_id": article_id,
                "base_score": 0.0,
                "lexical_score_norm": 0.0,
                "token_bm25_like_score": 0.0,
                "control_alignment_score": 0.0,
                "path_support_score": round(float(score), 4),
                "final_score": round(float(score) * 0.1, 4),
                "selected": False,
            }
        )

    related_articles = _dedupe_list(
        [str(v.get("article_id", "")).strip() for v in selected_requirements]
        + [str(v) for ob in selected_obligations for v in (ob.get("articles") or [])]
        + [str(v.get("article_id", "")).strip() for v in selected_article_candidates]
    )

    all_selected_scores = [float(v.get("_final_score", 0.0)) for v in req_candidates[:3]]
    if not all_selected_scores and selected_article_candidates:
        all_selected_scores = [float(v.get("_final_score", 0.0)) for v in selected_article_candidates[:3]]
    if selected_obligations and not all_selected_scores:
        all_selected_scores = [0.5]
    evidence_confidence = round(sum(all_selected_scores) / max(1, len(all_selected_scores)), 4) if all_selected_scores else 0.0

    req_count = len(selected_requirements)
    ob_count = len(selected_obligations)
    article_anchor_count = len(selected_article_candidates)
    if req_count > 0 and ob_count > 0:
        primary_type = "mixed"
    elif req_count > 0:
        primary_type = "requirement"
    elif ob_count > 0:
        primary_type = "obligation"
    elif article_anchor_count > 0:
        primary_type = "article"
    else:
        primary_type = "requirement"

    trace.sort(key=lambda x: (0 if x.get("selected") else 1, -float(x.get("final_score", 0.0))))
    trace = trace[:24]
    retrieval_debug = {
        "channel_hits": {
            "lexical_requirements": len(lexical_requirement_rows),
            "mandatory_requirements": len(anchor_requirement_rows),
            "lexical_obligations": len(obligation_rows),
            "lexical_articles": len(article_rows),
            "graph_path_articles": len(path_support),
            "multihop_articles": len(multihop_support),
        },
        "selected_counts": {
            "requirements": req_count,
            "obligations": ob_count,
            "article_anchors": article_anchor_count,
            "related_articles": len(related_articles),
        },
        "mandatory_articles": sorted(mandatory_set),
        "thresholds": {
            "final_threshold": float(final_threshold),
            "low_alignment_path_floor": 0.65,
            "fallback_guard_enabled": bool(mandatory_set),
        },
    }
    return {
        "requirement_evidence": selected_requirements,
        "obligation_evidence": selected_obligations,
        "related_articles": related_articles,
        "retrieval_trace": trace,
        "retrieval_debug": retrieval_debug,
        "evidence_confidence": float(evidence_confidence),
        "primary_evidence_type": primary_type,
    }
