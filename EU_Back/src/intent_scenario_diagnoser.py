"""Intent-oriented scenario diagnosis using KG evidence.

This module is designed for customer-facing pre-check questions:
- What is risky in this concrete usage scenario?
- Why is it risky?
- Which articles are related?
- What actions should be taken first?
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from src.c1_mapper import map_usecases_by_rules


PERSONAL_PHONE_RE = re.compile(r"\b01[0-9]-?[0-9]{3,4}-?[0-9]{4}\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


SCENARIO_RULES: List[Dict[str, Any]] = [
    {
        "id": "personal_data_in_prompt",
        "title": "개인정보 포함 데이터의 외부 AI 처리 위험",
        "severity": "high",
        "risk_points": 28,
        "keywords": [
            "개인정보",
            "이름",
            "연락처",
            "phone",
            "email",
            "고객님",
            "customer",
        ],
        "related_articles": ["Article 10", "Article 12"],
        "obligation_keywords": ["data governance", "record", "log", "traceability"],
        "recommended_action": "개인식별정보를 비식별/가명처리한 뒤 최소한의 데이터만 AI에 입력하고 처리기록을 남기세요.",
    },
    {
        "id": "eu_scope_cross_border",
        "title": "EU 고객 포함 시 규제 적용 가능성",
        "severity": "high",
        "risk_points": 24,
        "keywords": ["eu", "europe", "유럽", "european", "eu 고객"],
        "related_articles": ["Article 2", "Article 3"],
        "obligation_keywords": ["provider", "deployer", "obligation"],
        "recommended_action": "EU 고객 데이터가 포함되면 적용범위를 먼저 확인하고 내부 승인 절차를 거친 뒤 처리하세요.",
    },
    {
        "id": "automated_scoring",
        "title": "자동 점수/분류 산출의 설명가능성·감독 이슈",
        "severity": "medium",
        "risk_points": 18,
        "keywords": ["점수", "score", "scoring", "ranking", "감정 점수", "sentiment"],
        "related_articles": ["Article 14", "Article 15"],
        "obligation_keywords": ["human oversight", "accuracy", "robustness"],
        "recommended_action": "자동 점수는 보조지표로만 사용하고 인간 검토 및 오탐 대응 절차를 문서화하세요.",
    },
    {
        "id": "ai_generated_summary_disclosure",
        "title": "AI 생성 요약물의 투명성 고지 필요",
        "severity": "medium",
        "risk_points": 14,
        "keywords": ["요약", "요약 문장", "generated", "ai generated", "자동 생성", "보고서"],
        "related_articles": ["Article 13", "Article 50"],
        "obligation_keywords": ["transparen", "certain ai systems", "documentation"],
        "recommended_action": "보고서에 AI 사용 사실, 생성 범위, 검토 책임자를 명시해 투명성 고지를 하세요.",
    },
    {
        "id": "cloud_sharing_risk",
        "title": "사내 클라우드 공유 시 접근통제/추적성 이슈",
        "severity": "medium",
        "risk_points": 12,
        "keywords": ["클라우드", "cloud", "공유", "share", "업로드"],
        "related_articles": ["Article 12", "Article 15"],
        "obligation_keywords": ["record", "log", "traceability", "security"],
        "recommended_action": "접근권한 최소화, 보관기한 설정, 열람 로그 기록, 재식별 방지 정책을 적용하세요.",
    },
    {
        "id": "copyright_data_origin_unclear",
        "title": "학습·처리 데이터 출처 불명확성",
        "severity": "medium",
        "risk_points": 10,
        "keywords": ["데이터", "학습", "training", "dataset", "출처", "원본"],
        "related_articles": ["Article 53", "Article 54", "Article 55"],
        "obligation_keywords": ["copyright", "summary", "training"],
        "recommended_action": "데이터 출처/권리상태/보관정책을 정리하고 재사용 가능 범위를 명시하세요.",
    },
]


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _contains_regex(text: str) -> bool:
    return bool(PERSONAL_PHONE_RE.search(text) or EMAIL_RE.search(text))


def _query_article_context(graph: Any, article_ids: Sequence[str]) -> Dict[str, Dict[str, List[str]]]:
    ids = [str(a).strip() for a in article_ids if str(a).strip()]
    if not ids:
        return {}
    rows = graph.query(
        """
        MATCH (a:Article)
        WHERE a.id IN $article_ids
        OPTIONAL MATCH (o:Obligation)-[:DEFINED_IN]->(a)
        OPTIONAL MATCH (a)-[:IMPOSES]->(p:Penalty)
        OPTIONAL MATCH (src:Article)-[:REFERENCES]->(a)
        RETURN a.id AS article_id,
               collect(DISTINCT coalesce(o.id, o.description))[0..8] AS obligations,
               collect(DISTINCT coalesce(p.id, p.description))[0..6] AS penalties,
               collect(DISTINCT src.id)[0..6] AS referenced_by
        """,
        {"article_ids": ids},
    )
    out: Dict[str, Dict[str, List[str]]] = {}
    for row in rows:
        article_id = str(row.get("article_id", "")).strip()
        if not article_id:
            continue
        obligations = [str(v).strip() for v in (row.get("obligations") or []) if str(v).strip()]
        penalties = [str(v).strip() for v in (row.get("penalties") or []) if str(v).strip()]
        referenced_by = [str(v).strip() for v in (row.get("referenced_by") or []) if str(v).strip()]
        out[article_id] = {
            "obligations": obligations,
            "penalties": penalties,
            "referenced_by": referenced_by,
        }
    return out


def _query_obligations_by_keywords(graph: Any, keywords: Sequence[str], limit: int = 8) -> List[Dict[str, Any]]:
    kws = [str(k).strip().lower() for k in keywords if str(k).strip()]
    if not kws:
        return []
    rows = graph.query(
        """
        MATCH (o:Obligation)
        WHERE ANY(kw IN $keywords WHERE toLower(coalesce(o.id,'')) CONTAINS kw
                                   OR toLower(coalesce(o.description,'')) CONTAINS kw)
        OPTIONAL MATCH (o)-[:DEFINED_IN]->(a:Article)
        OPTIONAL MATCH (o)-[:ENFORCED_BY]->(i:Institution)
        RETURN o.id AS obligation_id,
               coalesce(o.description,'') AS description,
               collect(DISTINCT a.id)[0..6] AS articles,
               collect(DISTINCT i.id)[0..4] AS enforced_by
        LIMIT $limit
        """,
        {"keywords": kws, "limit": int(limit)},
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "obligation_id": str(row.get("obligation_id", "")).strip(),
                "description": str(row.get("description", "")).strip(),
                "articles": [str(v).strip() for v in (row.get("articles") or []) if str(v).strip()],
                "enforced_by": [str(v).strip() for v in (row.get("enforced_by") or []) if str(v).strip()],
            }
        )
    return out


def _build_kg_paths_for_issue(
    *,
    issue: Mapping[str, Any],
    article_context: Mapping[str, Mapping[str, List[str]]],
    obligation_evidence: Sequence[Mapping[str, Any]],
    max_paths: int = 12,
) -> List[Dict[str, Any]]:
    related_articles = [str(a).strip() for a in issue.get("related_articles", []) if str(a).strip()]
    out: List[Dict[str, Any]] = []
    seen = set()

    def add_path(
        *,
        path_type: str,
        path_text: str,
        article_id: str | None = None,
        obligation_id: str | None = None,
        penalty_id: str | None = None,
        institution_id: str | None = None,
        source_article_id: str | None = None,
    ) -> None:
        key = path_text.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        out.append(
            {
                "path_type": path_type,
                "path_text": path_text,
                "article_id": article_id or "",
                "source_article_id": source_article_id or "",
                "obligation_id": obligation_id or "",
                "penalty_id": penalty_id or "",
                "institution_id": institution_id or "",
            }
        )

    for obligation in obligation_evidence:
        obligation_id = str(obligation.get("obligation_id", "")).strip()
        obligation_articles = [
            str(a).strip()
            for a in obligation.get("articles", [])
            if str(a).strip() and (not related_articles or str(a).strip() in related_articles)
        ]
        institutions = [str(i).strip() for i in obligation.get("enforced_by", []) if str(i).strip()]
        for article_id in obligation_articles:
            add_path(
                path_type="obligation_article",
                path_text=f"(Obligation:{obligation_id}) -[DEFINED_IN]-> (Article:{article_id})",
                article_id=article_id,
                obligation_id=obligation_id,
            )
            for institution_id in institutions[:2]:
                add_path(
                    path_type="obligation_enforcement",
                    path_text=f"(Obligation:{obligation_id}) -[ENFORCED_BY]-> (Institution:{institution_id})",
                    article_id=article_id,
                    obligation_id=obligation_id,
                    institution_id=institution_id,
                )
            penalties = article_context.get(article_id, {}).get("penalties", [])
            for penalty_id in penalties[:2]:
                add_path(
                    path_type="obligation_article_penalty",
                    path_text=(
                        f"(Obligation:{obligation_id}) -[DEFINED_IN]-> (Article:{article_id}) "
                        f"-[IMPOSES]-> (Penalty:{penalty_id})"
                    ),
                    article_id=article_id,
                    obligation_id=obligation_id,
                    penalty_id=penalty_id,
                )
            for source_article_id in article_context.get(article_id, {}).get("referenced_by", [])[:2]:
                add_path(
                    path_type="article_reference",
                    path_text=f"(Article:{source_article_id}) -[REFERENCES]-> (Article:{article_id})",
                    article_id=article_id,
                    source_article_id=source_article_id,
                )

    for article_id in related_articles:
        penalties = article_context.get(article_id, {}).get("penalties", [])
        for penalty_id in penalties[:2]:
            add_path(
                path_type="article_penalty",
                path_text=f"(Article:{article_id}) -[IMPOSES]-> (Penalty:{penalty_id})",
                article_id=article_id,
                penalty_id=penalty_id,
            )
        for source_article_id in article_context.get(article_id, {}).get("referenced_by", [])[:2]:
            add_path(
                path_type="article_reference",
                path_text=f"(Article:{source_article_id}) -[REFERENCES]-> (Article:{article_id})",
                article_id=article_id,
                source_article_id=source_article_id,
            )

    return out[: max(1, int(max_paths))]


def _detect_signals(customer_text: str, user_question: str | None = None) -> List[Dict[str, Any]]:
    question = str(user_question or "").strip()
    body = str(customer_text or "").strip()
    combined = "\n".join([part for part in [question, body] if part]).strip()
    norm = _normalize_text(combined)

    issues: List[Dict[str, Any]] = []
    issue_idx = 1
    for rule in SCENARIO_RULES:
        hits = sorted({kw for kw in rule["keywords"] if kw.lower() in norm})
        if rule["id"] == "personal_data_in_prompt" and _contains_regex(combined):
            hits.append("phone_or_email_pattern")
        if not hits:
            continue
        sev = str(rule["severity"]).lower()
        issues.append(
            {
                "issue_id": f"INT-{issue_idx:02d}",
                "rule_id": rule["id"],
                "theme": rule["title"],
                "severity": sev,
                "risk_points": int(rule["risk_points"]),
                "trigger_terms": sorted(set(hits)),
                "finding": (
                    f"질문/문서에서 {', '.join(sorted(set(hits)))} 신호가 탐지되어 "
                    f"'{rule['title']}' 위험이 확인되었습니다."
                ),
                "related_articles": list(rule["related_articles"]),
                "obligation_keywords": list(rule["obligation_keywords"]),
                "recommended_action": rule["recommended_action"],
            }
        )
        issue_idx += 1

    issues.sort(key=lambda x: (SEVERITY_ORDER.get(str(x.get("severity", "low")), 9), -int(x.get("risk_points", 0))))
    return issues


def _score(issues: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    score = min(100, sum(int(item.get("risk_points", 0)) for item in issues))
    if score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"
    high_count = sum(1 for item in issues if str(item.get("severity", "")).lower() == "high")
    medium_count = sum(1 for item in issues if str(item.get("severity", "")).lower() == "medium")
    return {
        "risk_score": int(score),
        "risk_level": level,
        "issue_count": len(issues),
        "high_issue_count": high_count,
        "medium_issue_count": medium_count,
    }


def run_intent_scenario_assessment(
    *,
    graph: Any,
    customer_text: str,
    user_question: str | None = None,
    top_k_usecases: int = 3,
) -> Dict[str, Any]:
    """Run intent-oriented risk diagnosis and attach KG evidence."""
    issues = _detect_signals(customer_text=customer_text, user_question=user_question)
    summary = _score(issues)

    usecase_candidates = map_usecases_by_rules(customer_text, top_k=top_k_usecases)

    # KG evidence enrichment
    all_articles: List[str] = []
    for item in issues:
        all_articles.extend([str(a).strip() for a in item.get("related_articles", []) if str(a).strip()])
    article_context = _query_article_context(graph, sorted(set(all_articles)))

    enriched_issues: List[Dict[str, Any]] = []
    for item in issues:
        related_articles = [str(a).strip() for a in item.get("related_articles", []) if str(a).strip()]
        kg_article_evidence = []
        for article in related_articles:
            ctx = article_context.get(article, {})
            kg_article_evidence.append(
                {
                    "article_id": article,
                    "obligations": ctx.get("obligations", []),
                    "penalties": ctx.get("penalties", []),
                }
            )
        obligation_evidence = _query_obligations_by_keywords(
            graph=graph,
            keywords=item.get("obligation_keywords", []),
            limit=6,
        )
        kg_paths = _build_kg_paths_for_issue(
            issue=item,
            article_context=article_context,
            obligation_evidence=obligation_evidence,
            max_paths=12,
        )
        enriched_issues.append(
            {
                **item,
                "kg_article_evidence": kg_article_evidence,
                "obligation_evidence": obligation_evidence,
                "kg_paths": kg_paths,
            }
        )

    key_findings = [str(item.get("finding", "")).strip() for item in enriched_issues[:4] if str(item.get("finding", "")).strip()]
    next_actions = [str(item.get("recommended_action", "")).strip() for item in enriched_issues[:6] if str(item.get("recommended_action", "")).strip()]
    # Deduplicate actions while keeping order.
    seen = set()
    deduped_actions: List[str] = []
    for action in next_actions:
        key = action.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped_actions.append(action)

    report = {
        "meta": {
            "generated_at": _now(),
            "engine": "intent_scenario_diagnoser_v1",
            "top_k_usecases": int(top_k_usecases),
        },
        "input": {
            "question": str(user_question or "").strip(),
            "customer_text_preview": str(customer_text or "")[:500],
            "char_count": len(str(customer_text or "")),
        },
        "summary": {
            **summary,
            "key_findings": key_findings,
            "next_actions": deduped_actions,
        },
        "mapping": {
            "usecase_candidates": usecase_candidates,
        },
        "issues": enriched_issues,
    }
    return report


def write_intent_report(
    *,
    report: Mapping[str, Any],
    json_path: Path,
    summary_md_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_md_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report.get("summary", {}) if isinstance(report, Mapping) else {}
    issues = report.get("issues", []) if isinstance(report, Mapping) else []

    lines = [
        "# Intent Scenario Diagnosis",
        "",
        f"- Risk level: **{summary.get('risk_level', 'N/A')}**",
        f"- Risk score: `{summary.get('risk_score', 0)}`",
        f"- Issue count: `{summary.get('issue_count', 0)}` (high `{summary.get('high_issue_count', 0)}`, medium `{summary.get('medium_issue_count', 0)}`)",
        "",
        "## Why Risky",
        "",
    ]
    for finding in summary.get("key_findings", [])[:6]:
        lines.append(f"- {finding}")

    lines.extend(
        [
            "",
            "## Priority Actions",
            "",
        ]
    )
    for idx, action in enumerate(summary.get("next_actions", [])[:8], start=1):
        lines.append(f"{idx}. {action}")

    lines.extend(
        [
            "",
            "## Issues",
            "",
            "| ID | Severity | Theme | Related Articles | KG Path Count |",
            "|---|---|---|---|---:|",
        ]
    )
    for issue in issues[:20]:
        lines.append(
            f"| {issue.get('issue_id', '')} | {issue.get('severity', '')} | {issue.get('theme', '')} | "
            f"{', '.join(issue.get('related_articles', []) or [])} | {len(issue.get('kg_paths', []) or [])} |"
        )

    summary_md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
