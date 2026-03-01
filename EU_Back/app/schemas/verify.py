from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    system_name: str
    description: str


class VerifyIssue(BaseModel):
    issue_id: str
    theme: str
    severity: str
    evidence_status: Optional[str] = None
    evidence_status_label: Optional[str] = None
    related_articles: List[str] = Field(default_factory=list)
    related_article_briefs: List[str] = Field(default_factory=list)
    evidence_bullets: List[str] = Field(default_factory=list)
    primary_controls: List[str] = Field(default_factory=list)
    supporting_paths_preview: List[str] = Field(default_factory=list)
    usecase_hints: List[str] = Field(default_factory=list)
    timeline_hints: List[str] = Field(default_factory=list)
    finding: str = ""
    recommended_action: str = ""


class VerifyResponse(BaseModel):
    level: str
    score: int
    recommendations: List[str]
    retriever_version: Optional[str] = None
    key_findings: List[str] = Field(default_factory=list)
    issues: List[VerifyIssue] = Field(default_factory=list)
