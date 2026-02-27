from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from neo4j import GraphDatabase
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.verify import VerifyReport
from app.schemas.verify import VerifyIssue, VerifyRequest, VerifyResponse
from src.intent_rag_diagnoser import run_intent_rag_assessment


router = APIRouter()


class Neo4jQueryAdapter:
    """Minimal adapter that exposes graph.query(...) expected by Antigravity modules."""

    def __init__(self, *, uri: str, username: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(username, password))

    def query(self, cypher: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]

    def close(self) -> None:
        self._driver.close()


def _to_level_text(level: str) -> str:
    value = str(level or "").strip().upper()
    mapping = {
        "HIGH": "High Risk",
        "MEDIUM": "Medium Risk",
        "LOW": "Low Risk",
    }
    return mapping.get(value, "Unknown")


def _build_recommendations(report: Dict[str, Any]) -> List[str]:
    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    issues = report.get("issues", []) if isinstance(report, dict) else []

    next_actions = [str(v).strip() for v in (summary.get("next_actions") or []) if str(v).strip()]
    if next_actions:
        return next_actions[:6]

    actions: List[str] = []
    seen = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        action = str(issue.get("recommended_action", "")).strip()
        if not action:
            continue
        key = action.lower()
        if key in seen:
            continue
        seen.add(key)
        actions.append(action)
        if len(actions) >= 6:
            break
    if actions:
        return actions

    return ["진단 근거가 부족합니다. 입력 문서를 보강한 뒤 재진단하세요."]


@router.post("/chat")
def chat_with_ai(prompt: str) -> Dict[str, str]:
    return {"message": "Dummy AI Response for: " + prompt}


@router.post("/verify", response_model=VerifyResponse)
def verify_system(request: VerifyRequest, db: Session = Depends(get_db)) -> VerifyResponse:
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    retriever_mode = str(os.getenv("WEB_LAB_RETRIEVER_MODE", "v2")).strip().lower() or "v2"
    retriever_shadow = str(os.getenv("WEB_LAB_RETRIEVER_SHADOW", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    retriever_profile = str(os.getenv("WEB_LAB_RETRIEVER_PROFILE", "precision_first")).strip().lower() or "precision_first"

    customer_text = str(request.description or "").strip()
    user_question = str(request.system_name or "").strip()

    graph = None
    try:
        graph = Neo4jQueryAdapter(
            uri=neo4j_uri,
            username=neo4j_username,
            password=neo4j_password,
        )

        report = run_intent_rag_assessment(
            graph=graph,
            customer_text=customer_text,
            user_question=user_question,
            model_name=model_name,
            top_k_usecases=3,
            retriever_mode=retriever_mode,
            retriever_shadow=retriever_shadow,
            retriever_profile=retriever_profile,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Verify pipeline failed: {exc}")
    finally:
        if graph is not None:
            try:
                graph.close()
            except Exception:
                pass

    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    meta = report.get("meta", {}) if isinstance(report, dict) else {}
    issues = report.get("issues", []) if isinstance(report, dict) else []

    risk_level = str(summary.get("risk_level", "")).upper() or "UNKNOWN"
    risk_score = int(summary.get("risk_score", 0) or 0)
    recommendations = _build_recommendations(report)

    issue_rows: List[VerifyIssue] = []
    for issue in issues[:8]:
        if not isinstance(issue, dict):
            continue
        issue_rows.append(
            VerifyIssue(
                issue_id=str(issue.get("issue_id", "")).strip(),
                theme=str(issue.get("theme", "")).strip(),
                severity=str(issue.get("severity", "")).strip(),
                evidence_status=str(issue.get("evidence_status", "")).strip() or None,
                related_articles=[str(v).strip() for v in (issue.get("related_articles") or []) if str(v).strip()],
                finding=str(issue.get("finding", "")).strip(),
                recommended_action=str(issue.get("recommended_action", "")).strip(),
            )
        )

    db_report = VerifyReport(
        system_name=request.system_name,
        description=request.description,
        level=_to_level_text(risk_level),
        score=risk_score,
        recommendations=recommendations,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    return VerifyResponse(
        level=_to_level_text(risk_level),
        score=risk_score,
        recommendations=recommendations,
        retriever_version=str(meta.get("retriever_version", "")).strip() or None,
        key_findings=[str(v).strip() for v in (summary.get("key_findings") or []) if str(v).strip()][:6],
        issues=issue_rows,
    )
