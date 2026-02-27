"""Precision-first intent retriever v2 for KG-grounded diagnostics."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Mapping, Sequence


ARTICLE_ID_RE = re.compile(r"^article\s+(\d+)$", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9]{2,}|[\uac00-\ud7a3]{2,}", re.IGNORECASE)


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

    requirement_rows = _query_requirements_lexical(graph, keywords=effective_keywords, limit=96)
    obligation_rows = _query_obligations_lexical(graph, keywords=effective_keywords, limit=24)
    article_rows = _query_articles_lexical(graph, keywords=effective_keywords, limit=24)

    seed_articles = _dedupe_list(
        [str(v.get("article_id", "")).strip() for v in requirement_rows[:10]]
        + [str(v.get("article_id", "")).strip() for v in article_rows[:10]]
    )
    path_support = _query_path_support(graph, seed_articles=seed_articles)

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
        lexical_norm = min(1.0, float(row.get("base_score", 0.0)) / 12.0)
        path_score = float(path_support.get(article_id, 0.0))
        final_score = (
            0.35 * lexical_norm
            + 0.25 * token_overlap
            + 0.30 * control_alignment
            + 0.10 * path_score
        )
        low_alignment_drop = (
            control_alignment == 0.0
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
                }
            )
        elif control_alignment > 0.0 and final_score >= 0.42:
            aligned_pool.append(
                {
                    "req_id": req_id,
                    "req_text": req_text,
                    "article_id": article_id,
                    "score": int(round(final_score * 100)),
                    "_final_score": float(final_score),
                    "_control_alignment": float(control_alignment),
                }
            )

    req_candidates.sort(key=lambda x: (-float(x.get("_final_score", 0.0)), str(x.get("article_id", "")), str(x.get("req_id", ""))))
    selected_requirements: List[Dict[str, Any]] = []
    article_cap: Dict[str, int] = {}
    for item in req_candidates:
        article_id = str(item.get("article_id", ""))
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
        if len(selected_requirements) >= 8:
            break

    # Precision-first soft fallback: when strict threshold drops all requirements,
    # keep only control-aligned candidates with minimal semantic support.
    if not selected_requirements and aligned_pool:
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

    selected_obligations: List[Dict[str, Any]] = []
    for row in obligation_rows[:12]:
        desc = str(row.get("description", "")).strip()
        obligation_id = str(row.get("obligation_id", "")).strip()
        if not desc and not obligation_id:
            continue
        token_overlap = _overlap_ratio(_tokenize(desc + " " + obligation_id), focus_tokens)
        lexical_norm = min(1.0, float(row.get("base_score", 0.0)) / 8.0)
        ob_articles = [str(v).strip() for v in (row.get("articles") or []) if str(v).strip()]
        path_score = max([float(path_support.get(a, 0.0)) for a in ob_articles] + [0.0])
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
                "final_score": round(final_score, 4),
                "selected": bool(selected),
            }
        )
        if selected:
            selected_obligations.append(
                {
                    "obligation_id": obligation_id,
                    "description": desc,
                    "articles": _dedupe_list(ob_articles),
                    "enforced_by": _dedupe_list([str(v).strip() for v in (row.get("enforced_by") or []) if str(v).strip()]),
                }
            )
        if len(selected_obligations) >= 8:
            break

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
    )

    all_selected_scores = [float(v.get("_final_score", 0.0)) for v in req_candidates[:3]]
    if selected_obligations and not all_selected_scores:
        all_selected_scores = [0.5]
    evidence_confidence = round(sum(all_selected_scores) / max(1, len(all_selected_scores)), 4) if all_selected_scores else 0.0

    req_count = len(selected_requirements)
    ob_count = len(selected_obligations)
    if req_count > 0 and ob_count > 0:
        primary_type = "mixed"
    elif req_count > 0:
        primary_type = "requirement"
    elif ob_count > 0:
        primary_type = "obligation"
    else:
        primary_type = "requirement"

    trace.sort(key=lambda x: (0 if x.get("selected") else 1, -float(x.get("final_score", 0.0))))
    trace = trace[:24]
    retrieval_debug = {
        "channel_hits": {
            "lexical_requirements": len(requirement_rows),
            "lexical_obligations": len(obligation_rows),
            "lexical_articles": len(article_rows),
            "graph_path_articles": len(path_support),
        },
        "selected_counts": {
            "requirements": req_count,
            "obligations": ob_count,
            "related_articles": len(related_articles),
        },
        "thresholds": {
            "final_threshold": float(final_threshold),
            "low_alignment_path_floor": 0.65,
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
