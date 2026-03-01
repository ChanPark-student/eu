"""LLM intent parser + KG-grounded diagnoser for customer scenarios.

Design goal:
- LLM is used only to parse scenario intent signals.
- Final findings/actions are generated from KG retrieval evidence only.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Sequence

from src.intent_scenario_diagnoser import run_intent_scenario_assessment
from src.intent_retriever_v2 import retrieve_issue_evidence_v2


ARTICLE_ID_RE = re.compile(r"^article\s+(\d+)$", re.IGNORECASE)
ARTICLE_INLINE_RE = re.compile(
    r"(?:article|art\.?)\s*(\d{1,3})(?:\s*[-~to]+\s*(\d{1,3}))?",
    re.IGNORECASE,
)

KEYWORD_ARTICLE_HINTS: Dict[str, List[str]] = {
    "eu": ["Article 2", "Article 3"],
    "europe": ["Article 2", "Article 3"],
    "personal data": ["Article 10", "Article 12"],
    "privacy": ["Article 10", "Article 12"],
    "phone": ["Article 10", "Article 12"],
    "email": ["Article 10", "Article 12"],
    "data governance": ["Article 10"],
    "transparency": ["Article 13"],
    "ai generated": ["Article 13", "Article 50"],
    "scoring": ["Article 14", "Article 15"],
    "ranking": ["Article 14", "Article 15"],
    "oversight": ["Article 14"],
    "accuracy": ["Article 15"],
    "robustness": ["Article 15"],
    "cloud": ["Article 12", "Article 15"],
    "log": ["Article 12"],
    "traceability": ["Article 12"],
    "security": ["Article 12", "Article 15"],
    "encryption": ["Article 12", "Article 15"],
    "biometric": ["Article 10", "Article 13", "Article 14"],
    "face": ["Article 10", "Article 13"],
    "personality": ["Article 10", "Article 13", "Article 14"],
    "psychometric": ["Article 10", "Article 13", "Article 14"],
    "profiling": ["Article 10", "Article 13", "Article 14"],
    "recruit": ["Article 14", "Article 15"],
    "employment": ["Article 14", "Article 15"],
    "hiring": ["Article 14", "Article 15"],
    "race": ["Article 5", "Article 10", "Article 15"],
    "ethnicity": ["Article 10", "Article 15"],
    "bias": ["Article 10", "Article 15"],
    "demographic": ["Article 10", "Article 15"],
    "consent": ["Article 13"],
    "disclosure": ["Article 13", "Article 50"],
    "labeling": ["Article 13", "Article 50"],
    "synthetic": ["Article 13", "Article 50"],
    "deepfake": ["Article 13", "Article 50"],
    "voice": ["Article 13", "Article 50"],
    "voice cloning": ["Article 13", "Article 50"],
    "avatar": ["Article 13", "Article 50"],
    "third-party": ["Article 12", "Article 13"],
    "provenance": ["Article 12", "Article 13"],
    "supply chain": ["Article 12", "Article 13"],
    "cross-border": ["Article 2", "Article 3"],
    "distribution": ["Article 2", "Article 3"],
    "logo": ["Article 12", "Article 13"],
    "branding": ["Article 12", "Article 13"],
    "copyright": ["Article 53", "Article 54", "Article 55"],
    "training data": ["Article 53", "Article 54", "Article 55"],
    "gpai": ["Article 51", "Article 52", "Article 53", "Article 54", "Article 55"],
    "general-purpose ai": ["Article 51", "Article 52", "Article 53", "Article 54", "Article 55"],
    "foundation model": ["Article 51", "Article 52", "Article 53", "Article 54", "Article 55"],
    "high-risk": ["Article 6"],
    "high risk": ["Article 6"],
    "annex iii": ["Article 6"],
    "annex 3": ["Article 6"],
    "prohibited": ["Article 5"],
    "unacceptable risk": ["Article 5"],
    "social scoring": ["Article 5"],
    "subliminal": ["Article 5"],
    "manipulative": ["Article 5"],
    "right to explanation": ["Article 86"],
    "explanation request": ["Article 86"],
    "appeal": ["Article 86"],
    "contest decision": ["Article 86"],
    "penalty": ["Article 99"],
    "administrative fine": ["Article 99"],
    "fine": ["Article 99"],
    "sanction": ["Article 99"],
}

ARTICLE_BRIEF_MAP: Dict[str, str] = {
    "Article 2": "적용범위(영역/행위자) 판단 기준",
    "Article 3": "핵심 용어 정의(시스템/제공자/배포자 등)",
    "Article 5": "금지된 AI 관행(허용 불가 영역)",
    "Article 6": "고위험 AI 분류 기준(Annex III 연계)",
    "Article 9": "위험관리 체계 수립·운영 의무",
    "Article 10": "학습/검증/시험 데이터 거버넌스 의무",
    "Article 11": "기술문서화 의무",
    "Article 12": "로그/추적성 확보 의무",
    "Article 13": "사용자 고지·투명성·사용지침 의무",
    "Article 14": "인간 감독(Human oversight) 의무",
    "Article 15": "정확도·강건성·보안 의무",
    "Article 50": "일부 AI 시스템의 투명성 의무",
    "Article 51": "범용 AI 모델 분류 기준",
    "Article 52": "범용 AI 모델 제공자 관련 기본 의무",
    "Article 53": "범용 AI 모델 관련 문서·정보 의무",
    "Article 54": "범용 AI 모델 제공자 대표자 지정 의무",
    "Article 55": "범용 AI 모델 제공자 일반 의무",
    "Article 86": "자동화 판단 관련 설명 요청권",
    "Article 99": "행정벌/과징금(제재) 기준",
}
GENERIC_HEAVY_ARTICLES = {"Article 10", "Article 12", "Article 13", "Article 14", "Article 15"}
ANCHOR_PRIORITY_ARTICLES = {
    "Article 5",
    "Article 6",
    "Article 50",
    "Article 51",
    "Article 52",
    "Article 53",
    "Article 54",
    "Article 55",
    "Article 86",
    "Article 99",
}

CONTROL_KEYWORD_EXPANSIONS: Dict[str, List[str]] = {
    "biometric": ["data governance", "transparency", "human oversight"],
    "face": ["data governance", "transparency"],
    "personality": ["biometric", "transparency", "human oversight"],
    "psychometric": ["biometric", "transparency", "human oversight"],
    "profiling": ["biometric", "transparency", "human oversight"],
    "recruit": ["human oversight", "accuracy", "risk management"],
    "employment": ["human oversight", "accuracy", "risk management"],
    "hiring": ["human oversight", "accuracy"],
    "score": ["accuracy", "human oversight"],
    "ranking": ["accuracy", "human oversight"],
    "cloud": ["logging", "traceability", "security"],
    "storage": ["logging", "traceability", "security"],
    "security": ["logging", "traceability", "security"],
    "encryption": ["security", "traceability"],
    "consent": ["transparency"],
    "disclosure": ["transparency", "instructions for use"],
    "labeling": ["transparency", "instructions for use"],
    "ai generated": ["transparency", "instructions for use"],
    "synthetic": ["transparency", "instructions for use"],
    "deepfake": ["transparency", "instructions for use"],
    "voice cloning": ["transparency", "traceability"],
    "avatar": ["transparency", "traceability"],
    "third-party": ["traceability", "instructions for use", "data governance"],
    "provenance": ["traceability", "data governance"],
    "supply chain": ["traceability", "data governance"],
    "cross-border": ["transparency", "traceability"],
    "distribution": ["transparency", "traceability"],
    "logo": ["traceability", "instructions for use"],
    "branding": ["traceability", "instructions for use"],
    "training data": ["data governance"],
    "copyright": ["copyright"],
}

DEFAULT_RISK_POINTS = {"high": 24, "medium": 14, "low": 8}
OUT_OF_SCOPE_LAW_TERMS = ("gdpr", "ccpa", "hipaa", "pipl", "privacy act")
REQUIREMENT_NOISE_PATTERNS = (
    "the commission shall",
    "ai office shall",
    "member state considers",
    "implementing act",
    "template for a questionnaire",
    "market surveillance authority",
    "notified body",
    "common specification",
)
TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
THEME_KO_HINTS: Sequence[tuple[str, str]] = (
    ("facial biometric", "얼굴 생체정보 수집/처리"),
    ("biometric facial", "얼굴 생체정보 수집/처리"),
    ("processing of biometric", "생체정보 수집/처리"),
    ("biometric data collection", "생체정보 수집/처리"),
    ("psychometric", "자동 성향/심리 프로파일링"),
    ("personality", "자동 성향/심리 프로파일링"),
    ("psychological traits", "자동 성향/심리 프로파일링"),
    ("inference of psychological", "자동 성향/심리 프로파일링"),
    ("profiling", "프로파일링 리스크"),
    ("employment", "고용/채용 관련 자동 의사결정"),
    ("recruit", "고용/채용 관련 자동 의사결정"),
    ("hiring", "고용/채용 관련 자동 의사결정"),
    ("automated decision-making", "고용/채용 관련 자동 의사결정"),
    ("sensitive attribute", "민감속성(인종/민족 등) 추론"),
    ("race", "민감속성(인종/민족 등) 추론"),
    ("ethnicity", "민감속성(인종/민족 등) 추론"),
    ("data security", "데이터 보안/저장 리스크"),
    ("storage", "데이터 보안/저장 리스크"),
    ("consent", "동의/고지 미흡 리스크"),
    ("disclosure", "동의/고지 미흡 리스크"),
    ("accuracy claims", "정확도 주장/투명성 리스크"),
    ("undisclosed ai-generated content", "AI 생성물 미고지/라벨링 투명성 리스크"),
    ("labeling transparency", "AI 생성물 미고지/라벨링 투명성 리스크"),
    ("voice cloning", "음성 클로닝/합성음 사칭 리스크"),
    ("synthetic-voice impersonation", "음성 클로닝/합성음 사칭 리스크"),
    ("synthetic face", "합성 얼굴/아바타 오인 리스크"),
    ("avatar mistaken", "합성 얼굴/아바타 오인 리스크"),
    ("third-party ai tools", "서드파티 AI 도구 사용/컴플라이언스 체인 리스크"),
    ("provenance/compliance chain", "서드파티 AI 도구 사용/컴플라이언스 체인 리스크"),
    ("company logos", "기업 로고/브랜딩 노출 리스크"),
    ("branding in generated backgrounds", "기업 로고/브랜딩 노출 리스크"),
    ("cross-border applicability", "EU 배포/국경간 적용범위 리스크"),
    ("eu distribution", "EU 배포/국경간 적용범위 리스크"),
    ("real person's photo plus synthetic voice", "실존 인물 이미지+합성음 결합(딥페이크) 리스크"),
    ("deepfake of identifiable person", "실존 인물 이미지+합성음 결합(딥페이크) 리스크"),
    ("realistic ai-generated avatar", "실사형 AI 아바타/얼굴 애니메이션 오인 리스크"),
    ("face animation that mimics human appearance", "실사형 AI 아바타/얼굴 애니메이션 오인 리스크"),
    ("multiple third-party generative models", "다중 서드파티 생성형 모델 사용/근거체인 불명확 리스크"),
    ("unclear provenance/compliance", "다중 서드파티 생성형 모델 사용/근거체인 불명확 리스크"),
)

CONTROL_TERM_TO_CODE: Dict[str, str] = {
    "data governance": "data_governance",
    "transparency": "transparency",
    "human oversight": "oversight",
    "accuracy": "accuracy",
    "risk management": "risk_management",
    "logging": "traceability",
    "traceability": "traceability",
    "security": "security",
    "instructions for use": "instructions",
    "copyright": "copyright",
}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

AI_ACT_HYBRID_SIGNAL_RULES: List[Dict[str, Any]] = [
    {
        "id": "ai_generated_disclosure",
        "theme": "AI 생성물 미고지/라벨링 투명성 리스크",
        "severity": "high",
        "risk_points": 22,
        "keywords": ["ai로 만들", "ai generated", "synthetic", "deepfake", "라벨", "표시", "고지"],
        "retrieval_keywords": ["ai generated", "labeling", "transparency", "disclosure"],
    },
    {
        "id": "voice_cloning_impersonation",
        "theme": "음성 클로닝/합성음 사칭 리스크",
        "severity": "high",
        "risk_points": 22,
        "keywords": ["voice cloning", "cloning", "elevenlabs", "합성음", "목소리", "사칭"],
        "retrieval_keywords": ["voice cloning", "synthetic voice", "transparency", "traceability"],
    },
    {
        "id": "biometric_face_processing",
        "theme": "실사형 AI 아바타/얼굴 표현 오인 리스크",
        "severity": "high",
        "risk_points": 20,
        "keywords": ["셀카", "얼굴", "face", "avatar", "heygen", "입모양", "face animation"],
        "retrieval_keywords": ["biometric", "face", "transparency", "data governance", "human oversight"],
    },
    {
        "id": "employment_automation",
        "theme": "고용/채용 관련 자동 의사결정",
        "severity": "high",
        "risk_points": 22,
        "keywords": ["채용", "면접", "hiring", "recruit", "employment", "자동 평가"],
        "retrieval_keywords": ["employment", "recruitment", "human oversight", "accuracy", "risk management"],
    },
    {
        "id": "data_security_and_storage",
        "theme": "데이터 보안/저장 리스크",
        "severity": "medium",
        "risk_points": 14,
        "keywords": ["s3", "클라우드", "cloud", "저장", "암호화", "encryption", "접근권한"],
        "retrieval_keywords": ["security", "traceability", "logging", "data governance", "storage"],
    },
    {
        "id": "third_party_chain",
        "theme": "다중 서드파티 생성형 모델 사용/근거체인 불명확 리스크",
        "severity": "medium",
        "risk_points": 14,
        "keywords": ["midjourney", "heygen", "firefly", "third-party", "provenance", "외부 도구"],
        "retrieval_keywords": ["third-party", "provenance", "traceability", "instructions for use"],
    },
    {
        "id": "cross_border_eu",
        "theme": "EU 배포/국경간 적용범위 리스크",
        "severity": "medium",
        "risk_points": 13,
        "keywords": ["eu", "유럽", "독일", "프랑스", "cross-border", "distribution"],
        "retrieval_keywords": ["eu distribution", "cross-border", "provider", "deployer", "transparency"],
    },
    {
        "id": "sensitive_attribute_inference",
        "theme": "민감속성(인종/민족 등) 추론",
        "severity": "high",
        "risk_points": 18,
        "keywords": ["race", "ethnicity", "인종", "민족", "demographic", "민감속성"],
        "retrieval_keywords": ["sensitive attribute", "biometric categorisation", "data governance", "accuracy"],
    },
    {
        "id": "high_risk_classification_annex",
        "theme": "고위험 AI 분류(Annex III) 적용 리스크",
        "severity": "high",
        "risk_points": 20,
        "keywords": ["high-risk", "high risk", "annex iii", "annex 3", "critical infrastructure", "law enforcement"],
        "retrieval_keywords": ["high-risk classification", "annex iii", "risk management", "human oversight"],
    },
    {
        "id": "gpai_provider_obligations",
        "theme": "범용 AI(GPAI) 제공자 의무 리스크",
        "severity": "high",
        "risk_points": 20,
        "keywords": ["gpai", "general-purpose ai", "foundation model", "model card", "systemic risk model"],
        "retrieval_keywords": ["gpai obligations", "copyright", "training-data summary", "article 51", "article 55"],
    },
    {
        "id": "right_to_explanation_user_claim",
        "theme": "자동화 판단 설명요청권 대응 리스크",
        "severity": "medium",
        "risk_points": 14,
        "keywords": ["right to explanation", "explanation request", "appeal", "contest decision", "설명 요청"],
        "retrieval_keywords": ["right to explanation", "user transparency", "human oversight", "article 86"],
    },
    {
        "id": "penalty_enforcement_risk",
        "theme": "제재/벌금 노출 리스크",
        "severity": "medium",
        "risk_points": 13,
        "keywords": ["penalty", "fine", "sanction", "administrative fine", "벌금", "과징금", "제재"],
        "retrieval_keywords": ["penalties", "enforcement", "article 99", "non-compliance"],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json_payload(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return {}
    try:
        payload = json.loads(match.group(0))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


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
        text = str(item).strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _clip(text: str, max_len: int = 180) -> str:
    t = " ".join(str(text or "").strip().split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 3].rstrip() + "..."


def _article_brief(article_id: str) -> str:
    return str(ARTICLE_BRIEF_MAP.get(str(article_id or "").strip(), "")).strip()


def _format_article(article_id: str, include_brief: bool = True) -> str:
    article = _normalize_article_id(str(article_id or "").strip())
    if not article:
        return ""
    if not include_brief:
        return article
    brief = _article_brief(article)
    if not brief:
        return article
    return f"{article}({brief})"


def _render_article_refs(
    article_ids: Sequence[str],
    *,
    max_items: int = 3,
    include_brief: bool = True,
) -> str:
    normalized = _dedupe_list([_normalize_article_id(str(v)) for v in article_ids if str(v).strip()])
    normalized = [v for v in normalized if v][: max(1, int(max_items))]
    if not normalized:
        return "관련 조항"
    rendered = [item for item in (_format_article(v, include_brief=include_brief) for v in normalized) if item]
    return ", ".join(rendered) if rendered else "관련 조항"


def _article_brief_lines(article_ids: Sequence[str], *, max_items: int = 6) -> List[str]:
    out: List[str] = []
    normalized = _dedupe_list([_normalize_article_id(str(v)) for v in article_ids if str(v).strip()])
    for article in normalized[: max(1, int(max_items))]:
        brief = _article_brief(article)
        out.append(f"{article}: {brief}" if brief else article)
    return out


def _theme_prefers_generic_articles(theme: str) -> bool:
    theme_l = str(theme or "").lower()
    return any(
        token in theme_l
        for token in [
            "동의",
            "고지",
            "라벨",
            "label",
            "transparency",
            "disclosure",
            "consent",
            "voice",
            "deepfake",
            "avatar",
            "synthetic",
        ]
    )


def _apply_article_diversity(
    *,
    theme: str,
    article_ids: Sequence[str],
    enabled: bool = True,
) -> List[str]:
    normalized = _dedupe_list([_normalize_article_id(str(v)) for v in article_ids if str(v).strip()])
    normalized = [v for v in normalized if v]
    if not enabled or len(normalized) <= 2:
        return normalized
    if _theme_prefers_generic_articles(theme):
        return normalized

    non_generic = [v for v in normalized if v not in GENERIC_HEAVY_ARTICLES]
    generic = [v for v in normalized if v in GENERIC_HEAVY_ARTICLES]
    if non_generic:
        return _dedupe_list(non_generic + generic)
    return normalized


def _cap_related_articles(
    *,
    article_ids: Sequence[str],
    mandatory_articles: Sequence[str],
    max_items: int = 4,
) -> List[str]:
    normalized = _dedupe_list([_normalize_article_id(str(v)) for v in article_ids if str(v).strip()])
    normalized = [v for v in normalized if v]
    if not normalized:
        return []
    mandatory_set = {v for v in _dedupe_list([_normalize_article_id(str(v)) for v in mandatory_articles if str(v).strip()]) if v}
    if mandatory_set:
        mandatory_first = [v for v in normalized if v in mandatory_set][:3]
        others = [v for v in normalized if v not in mandatory_set][: max(0, int(max_items) - len(mandatory_first))]
        return _dedupe_list((mandatory_first + others)[: max(1, int(max_items))])
    return normalized[: max(1, int(max_items))]


LEGAL_STATE_EDUCATION_TERMS = (
    "education", "educational", "school", "student", "admission", "placement", "learning", "exam", "assessment",
    "교육", "학교", "학생", "입학", "배치", "학습", "평가", "시험", "진로",
)
LEGAL_STATE_WORKPLACE_TERMS = ("workplace", "employee", "employment", "worker", "직장", "고용", "근로", "직원")
LEGAL_STATE_EMOTION_TERMS = (
    "emotion", "emotional", "sentiment", "affect", "mood", "facial expression", "emotion inference",
    "감정", "정서", "표정", "감정 추론", "감정추론", "표정 분석",
)
LEGAL_STATE_CAMERA_TERMS = ("camera", "webcam", "video", "영상", "카메라", "웹캠")
LEGAL_STATE_EDU_DECISION_TERMS = (
    "access restriction", "admission", "placement", "evaluation", "score", "scoring", "ranking", "recommendation",
    "프로파일링", "접근 제한", "배치", "평가", "점수", "등급", "순위", "추천",
)
LEGAL_STATE_EXPLANATION_TERMS = (
    "right to explanation", "explanation request", "appeal", "contest decision", "explainability",
    "설명 요청", "설명권", "이의제기", "이의 제기",
)


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    lower = str(text or "").lower()
    return any(str(term).lower() in lower for term in terms)


def _classify_legal_state(
    *,
    customer_text: str,
    user_question: str,
) -> Dict[str, Any]:
    merged = f"{str(user_question or '')} {str(customer_text or '')}"
    compact = " ".join(merged.split())[:24000]
    lowered = compact.lower()

    states: List[str] = []
    required_articles: List[str] = []
    required_clauses: List[str] = []
    evidence_signals: List[str] = []

    in_education = _contains_any(lowered, LEGAL_STATE_EDUCATION_TERMS)
    in_workplace = _contains_any(lowered, LEGAL_STATE_WORKPLACE_TERMS)
    has_emotion = _contains_any(lowered, LEGAL_STATE_EMOTION_TERMS)
    has_camera = _contains_any(lowered, LEGAL_STATE_CAMERA_TERMS)
    has_inference = ("infer" in lowered) or ("추론" in lowered)
    has_edu_decision = in_education and _contains_any(lowered, LEGAL_STATE_EDU_DECISION_TERMS)

    # Prohibited practice: emotion inference in education/workplace contexts.
    if (in_education or in_workplace) and (has_emotion or (has_camera and has_inference)):
        states.append("prohibited_practice")
        required_articles.extend(["Article 5", "Article 86"])
        required_clauses.append("Article 5(1)(f)")
        evidence_signals.append("emotion_inference_in_education_or_workplace")

    # High-risk classification: Annex III education use-cases.
    if has_edu_decision:
        states.append("high_risk_classification")
        required_articles.extend(["Article 6", "Article 9", "Article 14"])
        required_clauses.extend(["Annex III 3(a)", "Annex III 3(b)"])
        evidence_signals.append("education_admission_placement_or_assessment")

    if _contains_any(lowered, ("gpai", "general-purpose ai", "foundation model", "범용 ai", "파운데이션 모델")):
        states.append("gpai_obligations")
        required_articles.extend(["Article 51", "Article 52", "Article 53", "Article 54", "Article 55"])
        evidence_signals.append("gpai_model_context")

    if _contains_any(lowered, LEGAL_STATE_EXPLANATION_TERMS):
        required_articles.append("Article 86")
        required_clauses.append("Article 86(1)")
        evidence_signals.append("explanation_right_context")

    if _contains_any(lowered, ("penalty", "fine", "sanction", "벌금", "과징금", "제재")):
        required_articles.append("Article 99")
        evidence_signals.append("penalty_or_sanction_context")

    normalized_articles = _dedupe_list([_normalize_article_id(v) for v in required_articles if _normalize_article_id(v)])
    normalized_clauses = _dedupe_list([str(v).strip() for v in required_clauses if str(v).strip()])
    states = _dedupe_list(states)

    return {
        "states": states,
        "required_articles": normalized_articles,
        "required_clauses": normalized_clauses,
        "evidence_signals": _dedupe_list(evidence_signals),
    }


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(str(text or "").lower())


def _is_noisy_requirement(req_id: str, req_text: str) -> bool:
    bag = f"{str(req_id or '').lower()} {str(req_text or '').lower()}"
    return any(pattern in bag for pattern in REQUIREMENT_NOISE_PATTERNS)


def _summarize_requirement_ko(req_text: str, req_id: str = "") -> str:
    bag = f"{str(req_id or '').lower()} {str(req_text or '').lower()}"
    if "생체정보 기반 민감속성 추론/분류 금지 요건" in req_text:
        return "생체정보 기반 민감속성 추론/분류 금지 요건"
    if "사용지침" in req_text:
        return "사용지침(Instructions for use) 제공 요건"
    if "인간 감독" in req_text:
        return "인간 감독(Human oversight) 요건"
    if "로그/추적성" in req_text:
        return "로그/추적성 확보 요건"
    if "보안 통제" in req_text:
        return "보안 통제 및 취약점 대응 요건"
    if "데이터 거버넌스" in req_text:
        return "학습/검증/시험 데이터 거버넌스 요건"
    if "투명성" in req_text or "사용자 고지" in req_text:
        return "사용자 고지 및 투명성 제공 요건"
    if "정확도" in req_text:
        return "정확도 및 성능 검증 요건"
    if "위험관리" in req_text:
        return "위험관리 체계 수립 요건"
    if "저작권" in req_text:
        return "저작권·학습데이터 공개 요건"

    if "biometric categorisation" in bag and "prohibit" in bag:
        return "생체정보 기반 민감속성 추론/분류 금지 요건"
    if "instructions for use" in bag or "instruction for use" in bag:
        return "사용지침(Instructions for use) 제공 요건"
    if "human oversight" in bag:
        return "인간 감독(Human oversight) 요건"
    if "traceability" in bag or "logging" in bag or "log" in bag or "provenance" in bag:
        return "로그/추적성 확보 요건"
    if "cybersecurity" in bag or "vulnerabilities" in bag or "security" in bag:
        return "보안 통제 및 취약점 대응 요건"
    if "training, validation and testing data sets" in bag or "data governance" in bag:
        return "학습/검증/시험 데이터 거버넌스 요건"
    if "transparency" in bag or "consent" in bag or "disclosure" in bag or "ai-generated" in bag or "synthetic" in bag:
        return "사용자 고지 및 투명성 제공 요건"
    if "accuracy" in bag:
        return "정확도 및 성능 검증 요건"
    if "risk management" in bag:
        return "위험관리 체계 수립 요건"
    if "copyright" in bag or "training-data summary" in bag:
        return "저작권·학습데이터 공개 요건"
    return "관련 준수 요건"


def _action_hint_from_label(label: str) -> str:
    text = str(label or "").strip()
    if "사용지침" in text:
        return "사용지침에 목적, 한계, 오탐 가능성, 담당자 연락처를 명시하세요."
    if "인간 감독" in text:
        return "자동 판단 단독 사용을 금지하고, 사람이 최종 승인/중단할 수 있게 절차를 두세요."
    if "데이터 거버넌스" in text:
        return "데이터 출처, 편향 통제, 보관기간, 삭제 기준을 문서화하세요."
    if "로그/추적성" in text:
        return "입력·출력·주요 판단 근거를 로그로 남기고 감사 가능 상태를 유지하세요."
    if "투명성" in text:
        return "사용자에게 AI 사용 사실, 처리 목적, 결과 한계를 사전에 고지하세요."
    if "정확도" in text:
        return "정확도 지표와 테스트 조건, 서브그룹 성능을 함께 공개하세요."
    if "보안 통제" in text:
        return "접근권한 최소화, 암호화, 취약점 점검 주기를 운영에 반영하세요."
    if "민감속성" in text:
        return "민감속성 추론/분류 기능은 비활성화하거나 법무 검토 후 제한적으로 사용하세요."
    if "저작권" in text:
        return "학습데이터 출처와 권리 상태, 공개 범위를 문서화하고 검증 기록을 남기세요."
    return "관련 통제를 운영 절차와 문서에 반영하세요."


def _render_signal_hint(trigger_terms: Sequence[str]) -> str:
    cleaned = [str(v).strip() for v in trigger_terms if str(v).strip()]
    if not cleaned:
        return ""
    compact = [v for v in cleaned if len(v) <= 32][:2]
    if not compact:
        return ""
    return f"입력 내용에서 '{', '.join(compact)}' 정황이 확인되어 "


def _control_code_from_label(label: str) -> str:
    text = str(label or "").strip()
    if not text:
        return ""
    if "민감속성" in text:
        return "sensitive_attr"
    if "인간 감독" in text:
        return "oversight"
    if "정확도" in text:
        return "accuracy"
    if "로그/추적성" in text:
        return "traceability"
    if "보안 통제" in text:
        return "security"
    if "데이터 거버넌스" in text:
        return "data_governance"
    if "투명성" in text:
        return "transparency"
    if "사용지침" in text:
        return "instructions"
    if "위험관리" in text:
        return "risk_management"
    if "저작권" in text:
        return "copyright"
    if "관련 준수 요건" in text:
        return "generic"
    return "generic"


def _control_label_from_code(code: str) -> str:
    mapping = {
        "data_governance": "학습/검증/시험 데이터 거버넌스 요건",
        "transparency": "사용자 고지 및 투명성 제공 요건",
        "instructions": "사용지침(Instructions for use) 제공 요건",
        "oversight": "인간 감독(Human oversight) 요건",
        "accuracy": "정확도 및 성능 검증 요건",
        "traceability": "로그/추적성 확보 요건",
        "security": "보안 통제 및 취약점 대응 요건",
        "risk_management": "위험관리 체계 수립 요건",
        "sensitive_attr": "생체정보 기반 민감속성 추론/분류 금지 요건",
        "copyright": "저작권·학습데이터 공개 요건",
        "generic": "관련 준수 요건",
    }
    return mapping.get(str(code or "").strip(), "관련 준수 요건")


def _theme_priority_control_codes(theme: str) -> List[str]:
    theme_l = str(theme or "").lower()
    if any(k in theme_l for k in ["gpai", "범용 ai", "범용", "general-purpose", "foundation model"]):
        return ["copyright", "traceability", "transparency", "instructions", "generic"]
    if any(k in theme_l for k in ["벌금", "과징금", "제재", "penalty", "fine", "sanction"]):
        return ["generic", "traceability", "transparency", "instructions"]
    if any(k in theme_l for k in ["설명요청", "설명 요청", "right to explanation", "explanation"]):
        return ["generic", "transparency", "oversight", "traceability"]
    if any(k in theme_l for k in ["고위험", "high-risk", "high risk", "annex iii", "annex 3"]):
        return ["risk_management", "data_governance", "oversight", "traceability", "generic"]
    if any(k in theme_l for k in ["금지", "prohibited", "unacceptable risk", "social scoring"]):
        return ["sensitive_attr", "generic", "oversight", "transparency"]
    if any(k in theme_l for k in ["고용", "채용", "employment", "recruit", "hiring"]):
        return ["oversight", "accuracy", "traceability", "instructions", "data_governance", "transparency"]
    if any(k in theme_l for k in ["생체", "biometric", "face"]):
        return ["data_governance", "oversight", "transparency", "instructions", "traceability", "security"]
    if any(k in theme_l for k in ["성향", "심리", "personality", "psychometric", "profiling"]):
        return ["oversight", "transparency", "data_governance", "instructions", "traceability", "accuracy"]
    if any(k in theme_l for k in ["민감속성", "race", "ethnicity", "sensitive attribute"]):
        return ["sensitive_attr", "data_governance", "accuracy", "oversight", "traceability", "security"]
    if any(k in theme_l for k in ["보안", "security", "storage", "저장", "cloud"]):
        return ["security", "traceability", "data_governance", "instructions", "transparency"]
    if any(k in theme_l for k in ["동의", "고지", "consent", "disclosure", "labeling", "ai generated"]):
        return ["transparency", "instructions", "traceability", "data_governance"]
    if any(k in theme_l for k in ["voice", "cloning", "deepfake", "synthetic", "avatar"]):
        return ["transparency", "instructions", "traceability", "oversight"]
    if any(k in theme_l for k in ["third-party", "provenance", "supply chain"]):
        return ["traceability", "instructions", "data_governance", "transparency"]
    if any(k in theme_l for k in ["cross-border", "distribution", "eu 배포"]):
        return ["transparency", "traceability", "instructions", "data_governance"]
    if any(k in theme_l for k in ["logo", "branding"]):
        return ["traceability", "instructions", "transparency"]
    return ["data_governance", "transparency", "traceability", "oversight", "instructions"]


def _expected_control_codes(
    *,
    theme: str,
    retrieval_keywords: Sequence[str],
    trigger_terms: Sequence[str],
) -> List[str]:
    expected = set(_theme_priority_control_codes(theme)[:3])
    bag = " ".join(
        [str(theme or "").lower()]
        + [str(v).lower() for v in retrieval_keywords]
        + [str(v).lower() for v in trigger_terms]
    )
    for key, expansions in CONTROL_KEYWORD_EXPANSIONS.items():
        if key in bag:
            for term in expansions:
                code = CONTROL_TERM_TO_CODE.get(str(term).strip().lower())
                if code:
                    expected.add(code)
    ordered = _theme_priority_control_codes(theme) + sorted(expected)
    return _dedupe_list([str(v).strip() for v in ordered if str(v).strip() and v in expected])


def _evidence_control_codes(
    *,
    requirement_evidence: Sequence[Mapping[str, Any]],
    obligation_evidence: Sequence[Mapping[str, Any]],
) -> List[str]:
    out: List[str] = []
    for item in requirement_evidence[:6]:
        label = _summarize_requirement_ko(str(item.get("req_text", "")), str(item.get("req_id", "")))
        code = _control_code_from_label(label)
        if code:
            out.append(code)
    for item in obligation_evidence[:4]:
        label = _summarize_requirement_ko(
            str(item.get("description", "")).strip() or str(item.get("obligation_id", "")).strip(),
            str(item.get("obligation_id", "")).strip(),
        )
        code = _control_code_from_label(label)
        if code:
            out.append(code)
    return _dedupe_list(out)


def _downgrade_severity(severity: str) -> str:
    sev = str(severity or "medium").strip().lower()
    if sev == "high":
        return "medium"
    if sev == "medium":
        return "low"
    return "low"


def _evaluate_evidence_alignment(
    *,
    theme: str,
    retrieval_keywords: Sequence[str],
    trigger_terms: Sequence[str],
    requirement_evidence: Sequence[Mapping[str, Any]],
    obligation_evidence: Sequence[Mapping[str, Any]],
    related_articles: Sequence[str] | None = None,
    mandatory_articles: Sequence[str] | None = None,
) -> Dict[str, Any]:
    expected_codes = _expected_control_codes(
        theme=theme,
        retrieval_keywords=retrieval_keywords,
        trigger_terms=trigger_terms,
    )
    actual_codes = _evidence_control_codes(
        requirement_evidence=requirement_evidence,
        obligation_evidence=obligation_evidence,
    )
    matched_codes = [code for code in expected_codes if code in set(actual_codes)]
    has_any_evidence = bool(requirement_evidence or obligation_evidence)
    actual_articles = _dedupe_list(
        [_normalize_article_id(str(v)) for v in (related_articles or []) if str(v).strip()]
        + [_normalize_article_id(str(item.get("article_id", ""))) for item in requirement_evidence]
        + [
            _normalize_article_id(str(article_id))
            for item in obligation_evidence
            for article_id in (item.get("articles") or [])
            if str(article_id).strip()
        ]
    )
    actual_articles = [v for v in actual_articles if v]
    mandatory_set = {
        v
        for v in _dedupe_list(
            [_normalize_article_id(str(v)) for v in (mandatory_articles or []) if str(v).strip()]
        )
        if v
    }
    mandatory_hit = bool(set(actual_articles) & mandatory_set) if mandatory_set else True

    if not has_any_evidence:
        status = "insufficient"
    elif mandatory_set and not mandatory_hit:
        status = "mismatch_downgraded"
    elif expected_codes and not matched_codes:
        status = "mismatch_downgraded"
    else:
        status = "grounded"

    return {
        "status": status,
        "expected_codes": expected_codes,
        "actual_codes": actual_codes,
        "matched_codes": matched_codes,
        "actual_articles": actual_articles,
        "mandatory_articles": sorted(mandatory_set),
        "mandatory_hit": bool(mandatory_hit),
        "expected_labels": [_control_label_from_code(code) for code in expected_codes[:4]],
        "matched_labels": [_control_label_from_code(code) for code in matched_codes[:4]],
    }


def _issue_token_bag(issue: Mapping[str, Any]) -> set[str]:
    theme = str(issue.get("theme", "")).strip().lower()
    retrieval_keywords = [str(v).strip().lower() for v in (issue.get("retrieval_keywords") or []) if str(v).strip()]
    trigger_terms = [str(v).strip().lower() for v in (issue.get("trigger_terms") or []) if str(v).strip()]
    bag = set(_tokenize(theme))
    for text in retrieval_keywords + trigger_terms:
        bag.update(_tokenize(text))
    return bag


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def _merge_issue_signals(base: Dict[str, Any], candidate: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    base_sev = str(out.get("severity", "low")).lower()
    cand_sev = str(candidate.get("severity", "low")).lower()
    if SEVERITY_ORDER.get(cand_sev, 9) < SEVERITY_ORDER.get(base_sev, 9):
        out["severity"] = cand_sev
    out["risk_points"] = max(int(out.get("risk_points", 0) or 0), int(candidate.get("risk_points", 0) or 0))
    out["trigger_terms"] = _dedupe_list(
        [str(v).strip() for v in (out.get("trigger_terms") or []) if str(v).strip()]
        + [str(v).strip() for v in (candidate.get("trigger_terms") or []) if str(v).strip()]
    )
    out["retrieval_keywords"] = _dedupe_list(
        [str(v).strip().lower() for v in (out.get("retrieval_keywords") or []) if str(v).strip()]
        + [str(v).strip().lower() for v in (candidate.get("retrieval_keywords") or []) if str(v).strip()]
    )
    out["related_articles"] = _dedupe_list(
        [str(v).strip() for v in (out.get("related_articles") or []) if str(v).strip()]
        + [str(v).strip() for v in (candidate.get("related_articles") or []) if str(v).strip()]
    )
    return out


def _dedupe_overlapping_issue_signals(issues: Sequence[Mapping[str, Any]], max_items: int = 6) -> List[Dict[str, Any]]:
    # Merge near-duplicate intent issues to avoid score inflation from one scenario split into many variants.
    rows = [dict(v) for v in issues if isinstance(v, Mapping)]
    rows.sort(
        key=lambda x: (
            SEVERITY_ORDER.get(str(x.get("severity", "low")).lower(), 9),
            -int(x.get("risk_points", 0) or 0),
        )
    )

    kept: List[Dict[str, Any]] = []
    for item in rows:
        item_theme = _normalize_theme(str(item.get("theme", "")))
        item_bag = _issue_token_bag(item)
        merged = False
        for idx, existing in enumerate(kept):
            existing_theme = _normalize_theme(str(existing.get("theme", "")))
            existing_bag = _issue_token_bag(existing)
            is_same_theme = item_theme == existing_theme
            overlap = _jaccard(item_bag, existing_bag)
            should_merge = is_same_theme or overlap >= 0.68
            if should_merge:
                kept[idx] = _merge_issue_signals(existing, item)
                merged = True
                break
        if merged:
            continue
        if len(kept) < max(1, int(max_items)):
            kept.append(dict(item))
    return kept


def _extract_rule_based_issue_signals(
    *,
    customer_text: str,
    user_question: str | None,
) -> List[Dict[str, Any]]:
    question = str(user_question or "").strip().lower()
    body = str(customer_text or "").strip().lower()
    bag = " ".join([v for v in [question, body] if v]).strip()
    if not bag:
        return []

    issues: List[Dict[str, Any]] = []
    for rule in AI_ACT_HYBRID_SIGNAL_RULES:
        keywords = [str(v).strip().lower() for v in (rule.get("keywords") or []) if str(v).strip()]
        hits = [kw for kw in keywords if kw in bag]
        if not hits:
            continue
        retrieval_keywords = _dedupe_list(
            [str(v).strip().lower() for v in (rule.get("retrieval_keywords") or []) if str(v).strip()]
            + hits[:4]
        )
        issues.append(
            {
                "theme": str(rule.get("theme", "")).strip() or "사용자 맥락 기반 AI Act 리스크",
                "severity": str(rule.get("severity", "medium")).strip().lower(),
                "risk_points": int(rule.get("risk_points", DEFAULT_RISK_POINTS["medium"]) or DEFAULT_RISK_POINTS["medium"]),
                "trigger_terms": _dedupe_list(hits[:6]),
                "retrieval_keywords": retrieval_keywords,
            }
        )
    return issues


def _merge_hybrid_extracted_issues(
    *,
    llm_issues: Sequence[Mapping[str, Any]],
    rule_issues: Sequence[Mapping[str, Any]],
    max_items: int = 6,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in list(llm_issues or []) + list(rule_issues or []):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "theme": str(item.get("theme", "")).strip() or "사용자 맥락 기반 AI Act 리스크",
                "severity": str(item.get("severity", "medium")).strip().lower() or "medium",
                "risk_points": int(item.get("risk_points", 0) or 0),
                "trigger_terms": _dedupe_list(
                    [str(v).strip() for v in (item.get("trigger_terms") or []) if str(v).strip()]
                ),
                "retrieval_keywords": _dedupe_list(
                    [str(v).strip().lower() for v in (item.get("retrieval_keywords") or []) if str(v).strip()]
                ),
                "related_articles": _dedupe_list(
                    [str(v).strip() for v in (item.get("related_articles") or []) if str(v).strip()]
                ),
            }
        )
    return _dedupe_overlapping_issue_signals(rows, max_items=max_items)


def _prioritize_requirements_for_theme(
    *,
    theme: str,
    requirement_evidence: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    theme_l = str(theme or "").lower()
    priority_codes = _theme_priority_control_codes(theme)
    rows: List[Dict[str, Any]] = [dict(v) for v in requirement_evidence if isinstance(v, Mapping)]
    if not rows:
        return []

    def priority_index(item: Mapping[str, Any]) -> int:
        label = _summarize_requirement_ko(str(item.get("req_text", "")), str(item.get("req_id", "")))
        code = _control_code_from_label(label)
        if code in priority_codes:
            return priority_codes.index(code)
        if code == "generic":
            return len(priority_codes) + 3
        return len(priority_codes) + 1

    def extra(item: Mapping[str, Any]) -> int:
        label = _summarize_requirement_ko(str(item.get("req_text", "")), str(item.get("req_id", "")))
        article = str(item.get("article_id", "")).strip()
        score = 0
        if any(k in theme_l for k in ["고용", "채용", "employment", "recruit", "hiring"]):
            if "인간 감독" in label:
                score += 6
            if "정확도" in label:
                score += 5
            if article in {"Article 14", "Article 15"}:
                score += 2
            if "사용지침" in label:
                score -= 2
        if any(k in theme_l for k in ["성향", "심리", "personality", "psychometric", "profiling"]):
            if "인간 감독" in label:
                score += 5
            if "투명성" in label:
                score += 4
            if "사용지침" in label:
                score -= 1
        if any(k in theme_l for k in ["보안", "security", "storage", "저장"]):
            if "보안 통제" in label:
                score += 6
            if "로그/추적성" in label:
                score += 5
            if article in {"Article 12", "Article 15"}:
                score += 2
        if any(k in theme_l for k in ["동의", "고지", "consent", "disclosure"]):
            if "투명성" in label:
                score += 6
            if "사용지침" in label:
                score += 2
        if any(k in theme_l for k in ["민감속성", "race", "ethnicity", "sensitive attribute"]):
            if "민감속성" in label:
                score += 8
            if "데이터 거버넌스" in label:
                score += 3
        if any(k in theme_l for k in ["생체", "biometric", "face"]):
            if "데이터 거버넌스" in label:
                score += 4
            if "투명성" in label:
                score += 3
        return score

    rows.sort(
        key=lambda item: (
            priority_index(item),
            -(int(item.get("score", 0) or 0) + extra(item)),
            str(item.get("article_id", "")),
            str(item.get("req_id", "")),
        )
    )
    return rows


def _select_primary_requirement_for_theme(
    *,
    theme: str,
    requirement_evidence: Sequence[Mapping[str, Any]],
) -> Dict[str, Any] | None:
    rows = [dict(v) for v in requirement_evidence if isinstance(v, Mapping)]
    if not rows:
        return None
    priority_codes = _theme_priority_control_codes(theme)

    def key(item: Mapping[str, Any]) -> tuple[int, int, str, str]:
        label = _summarize_requirement_ko(str(item.get("req_text", "")), str(item.get("req_id", "")))
        code = _control_code_from_label(label)
        p = priority_codes.index(code) if code in priority_codes else len(priority_codes) + 1
        return (
            p,
            -int(item.get("score", 0) or 0),
            str(item.get("article_id", "")),
            str(item.get("req_id", "")),
        )

    rows.sort(key=key)
    return rows[0]


def _rank_requirement_evidence(
    *,
    requirements: Sequence[Mapping[str, Any]],
    focus_keywords: Sequence[str],
    preferred_articles: Sequence[str],
    max_items: int = 6,
) -> List[Dict[str, Any]]:
    focus_phrases = [str(v).strip().lower() for v in focus_keywords if str(v).strip()]
    focus_token_set = set(_tokenize(" ".join(focus_phrases)))
    preferred = {_normalize_article_id(str(v)) for v in preferred_articles if str(v).strip()}

    scored: List[Dict[str, Any]] = []
    seen = set()
    for item in requirements:
        req_id = str(item.get("req_id", "")).strip()
        req_text = str(item.get("req_text", "")).strip()
        article_id = _normalize_article_id(str(item.get("article_id", "")).strip())
        if not req_text or not article_id:
            continue
        uniq = (article_id.lower(), req_id.lower(), req_text.lower())
        if uniq in seen:
            continue
        seen.add(uniq)

        bag = f"{req_id} {req_text}".lower()
        base_score = int(item.get("score", 0) or 0)
        phrase_score = sum(4 if " " in kw else 2 for kw in focus_phrases if kw in bag)
        token_overlap = len(set(_tokenize(bag)) & focus_token_set)
        article_bonus = 3 if article_id in preferred else 0
        if _is_noisy_requirement(req_id=req_id, req_text=req_text):
            continue
        score = base_score + phrase_score + min(6, token_overlap) + article_bonus
        if score < 3:
            continue

        scored.append(
            {
                "req_id": req_id,
                "req_text": req_text,
                "article_id": article_id,
                "score": int(score),
            }
        )

    scored.sort(key=lambda x: (-int(x.get("score", 0)), str(x.get("article_id", "")), str(x.get("req_id", ""))))

    # Keep diversity by limiting too many requirements from the same article.
    per_article_cap = 2
    article_counts: Dict[str, int] = {}
    selected: List[Dict[str, Any]] = []
    for item in scored:
        article_id = str(item.get("article_id", ""))
        if article_counts.get(article_id, 0) >= per_article_cap:
            continue
        article_counts[article_id] = article_counts.get(article_id, 0) + 1
        selected.append(item)
        if len(selected) >= max(1, int(max_items)):
            break
    return selected


def _normalize_theme(theme: str) -> str:
    text = str(theme or "").strip()
    if not text:
        return "Scenario risk"
    lowered = text.lower()
    if any(term in lowered for term in OUT_OF_SCOPE_LAW_TERMS):
        return "사용자 맥락 기반 AI Act 리스크"
    # Prefer Korean labels for common English themes.
    if all(ord(ch) < 128 for ch in text):
        for hint, label in THEME_KO_HINTS:
            if hint in lowered:
                return label
        if any(term in lowered for term in ["voice", "cloning", "deepfake", "synthetic voice"]):
            return "합성음/음성 사칭(딥페이크) 리스크"
        if any(term in lowered for term in ["avatar", "face animation", "synthetic face"]):
            return "실사형 AI 아바타/얼굴 표현 오인 리스크"
        if any(term in lowered for term in ["third-party", "provenance", "supply chain"]):
            return "서드파티 AI 도구 사용/근거체인 불명확 리스크"
        if any(term in lowered for term in ["labeling", "disclosure", "ai-generated", "ai generated"]):
            return "AI 생성물 미고지/라벨링 투명성 리스크"
        if any(term in lowered for term in ["logo", "branding"]):
            return "기업 로고/브랜딩 노출 리스크"
        if any(term in lowered for term in ["distribution", "cross-border", "eu market", "eu distribution"]):
            return "EU 배포/국경간 적용범위 리스크"
        return "사용자 맥락 기반 AI Act 리스크"
    return text


def _expand_retrieval_keywords(
    *,
    theme: str,
    retrieval_keywords: Sequence[str],
    trigger_terms: Sequence[str],
) -> List[str]:
    out = _dedupe_list([str(v).strip().lower() for v in retrieval_keywords if str(v).strip()])
    bag = " ".join(
        [str(theme or "").lower()]
        + [str(v).lower() for v in retrieval_keywords]
        + [str(v).lower() for v in trigger_terms]
    )
    for token, expansions in CONTROL_KEYWORD_EXPANSIONS.items():
        if token in bag:
            out.extend(expansions)
    return _dedupe_list(out)


def _keyword_article_candidates(keywords: Sequence[str]) -> List[str]:
    out: List[str] = []
    for kw in keywords:
        k = str(kw or "").strip().lower()
        if not k:
            continue
        for hint, article_ids in KEYWORD_ARTICLE_HINTS.items():
            if hint in k:
                out.extend(article_ids)
    return _dedupe_list(out)


def _extract_explicit_article_mentions(*texts: str, max_article: int = 120) -> List[str]:
    out: List[str] = []
    for text in texts:
        bag = str(text or "")
        for m in ARTICLE_INLINE_RE.finditer(bag):
            try:
                start = int(m.group(1))
            except Exception:
                continue
            end_raw = str(m.group(2) or "").strip()
            if not (1 <= start <= int(max_article)):
                continue
            if end_raw:
                try:
                    end = int(end_raw)
                except Exception:
                    end = start
                lo, hi = min(start, end), max(start, end)
                if 1 <= lo <= int(max_article) and 1 <= hi <= int(max_article) and (hi - lo) <= 10:
                    out.extend([f"Article {v}" for v in range(lo, hi + 1)])
                    continue
            out.append(f"Article {start}")
    return _dedupe_list([_normalize_article_id(v) for v in out if _normalize_article_id(v)])


def _derive_mandatory_articles(
    *,
    theme: str,
    retrieval_keywords: Sequence[str],
    trigger_terms: Sequence[str],
    legal_state_required_articles: Sequence[str],
    hint_articles: Sequence[str],
    query_articles: Sequence[str],
    usecase_candidates: Sequence[Mapping[str, Any]],
) -> List[str]:
    texts = [str(theme or "")] + [str(v or "") for v in retrieval_keywords] + [str(v or "") for v in trigger_terms]
    bag = " ".join(texts).lower()
    mandatory: List[str] = []
    mandatory.extend([str(v).strip() for v in legal_state_required_articles if str(v).strip()])

    # Explicit user mentions (e.g., "Article 86", "Art.51-55") should always be preserved.
    mandatory.extend(_extract_explicit_article_mentions(*texts))

    axis_rules: List[tuple[List[str], List[str]]] = [
        (["prohibited", "unacceptable risk", "social scoring", "subliminal", "manipulative"], ["Article 5"]),
        (["high-risk", "high risk", "annex iii", "annex 3", "critical infrastructure"], ["Article 6"]),
        (["gpai", "general-purpose ai", "foundation model", "systemic risk model"], ["Article 51", "Article 52", "Article 53", "Article 54", "Article 55"]),
        (["right to explanation", "explanation request", "appeal", "contest decision", "설명 요청"], ["Article 86"]),
        (["penalty", "fine", "sanction", "administrative fine", "벌금", "과징금", "제재"], ["Article 99"]),
    ]
    for keys, article_ids in axis_rules:
        if any(k in bag for k in keys):
            mandatory.extend(article_ids)

    # Annex/high-risk use-case evidence should map back to Art.6 classification axis.
    for item in usecase_candidates:
        if not isinstance(item, Mapping):
            continue
        annex_point = str(item.get("annex_point", "")).strip()
        risk_categories = [str(v).strip().lower() for v in (item.get("risk_categories") or []) if str(v).strip()]
        if annex_point or any("high-risk" in v or "high risk" in v for v in risk_categories):
            mandatory.append("Article 6")

    normalized = _dedupe_list([_normalize_article_id(v) for v in mandatory if _normalize_article_id(v)])
    if not normalized:
        return []

    def _article_sort_key(article_id: str) -> tuple[int, str]:
        m = ARTICLE_ID_RE.match(str(article_id or ""))
        if not m:
            return (9999, str(article_id))
        return (int(m.group(1)), str(article_id))

    normalized.sort(key=_article_sort_key)
    return normalized[:10]


def _query_articles_by_keywords(graph: Any, keywords: Sequence[str], limit: int = 20) -> List[str]:
    kws = [str(k).strip().lower() for k in keywords if str(k).strip()]
    if not kws:
        return []
    rows = graph.query(
        """
        MATCH (a:Article)
        OPTIONAL MATCH (c:ComplianceReq)-[:DEFINED_IN]->(a)
        WITH a,
             collect(DISTINCT toLower(coalesce(c.text,''))) AS c_texts,
             collect(DISTINCT toLower(coalesce(c.id,''))) AS c_ids
        OPTIONAL MATCH (o:Obligation)-[:DEFINED_IN]->(a)
        WITH a, c_texts, c_ids,
             collect(DISTINCT toLower(coalesce(o.description,''))) AS o_descs,
             collect(DISTINCT toLower(coalesce(o.id,''))) AS o_ids
        OPTIONAL MATCH (a)-[:IMPOSES]->(p:Penalty)
        WITH a, c_texts, c_ids, o_descs, o_ids,
             collect(DISTINCT toLower(coalesce(p.description,''))) AS p_descs
        WITH a,
             reduce(score = 0, kw IN $keywords |
                 score +
                 CASE WHEN ANY(v IN c_texts WHERE v CONTAINS kw) THEN 4 ELSE 0 END +
                 CASE WHEN ANY(v IN c_ids WHERE v CONTAINS kw) THEN 3 ELSE 0 END +
                 CASE WHEN ANY(v IN o_descs WHERE v CONTAINS kw) THEN 2 ELSE 0 END +
                 CASE WHEN ANY(v IN o_ids WHERE v CONTAINS kw) THEN 1 ELSE 0 END +
                 CASE WHEN ANY(v IN p_descs WHERE v CONTAINS kw) THEN 1 ELSE 0 END +
                 CASE WHEN toLower(coalesce(a.id,'')) = kw THEN 1 ELSE 0 END
             ) AS score
        WHERE score > 0
        RETURN a.id AS article_id, score
        ORDER BY score DESC, article_id ASC
        LIMIT $limit
        """,
        {"keywords": kws, "limit": int(limit)},
    )
    out: List[str] = []
    for row in rows:
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        if article_id:
            out.append(article_id)
    return _dedupe_list(out)


def _query_requirements_by_keywords(graph: Any, keywords: Sequence[str], limit: int = 12) -> List[Dict[str, Any]]:
    kws = [str(k).strip().lower() for k in keywords if str(k).strip()]
    if not kws:
        return []
    rows = graph.query(
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
                "score": int(row.get("score", 0) or 0),
            }
        )
    return out


def _query_article_context(graph: Any, article_ids: Sequence[str]) -> Dict[str, Dict[str, List[str]]]:
    ids = [_normalize_article_id(a) for a in article_ids]
    ids = [item for item in ids if item]
    if not ids:
        return {}
    rows = graph.query(
        """
        MATCH (a:Article)
        WHERE a.id IN $article_ids
        OPTIONAL MATCH (o:Obligation)-[:DEFINED_IN]->(a)
        OPTIONAL MATCH (a)-[:IMPOSES]->(p:Penalty)
        OPTIONAL MATCH (src:Article)-[:REFERENCES]->(a)
        OPTIONAL MATCH (c:ComplianceReq)-[:DEFINED_IN]->(a)
        RETURN a.id AS article_id,
               collect(DISTINCT coalesce(o.id, o.description))[0..8] AS obligations,
               collect(DISTINCT coalesce(p.id, p.description))[0..6] AS penalties,
               collect(DISTINCT src.id)[0..6] AS referenced_by,
               collect(DISTINCT coalesce(c.text, c.id))[0..6] AS requirements
        """,
        {"article_ids": ids},
    )
    out: Dict[str, Dict[str, List[str]]] = {}
    for row in rows:
        article_id = _normalize_article_id(str(row.get("article_id", "")))
        if not article_id:
            continue
        obligations = [str(v).strip() for v in (row.get("obligations") or []) if str(v).strip()]
        penalties = [str(v).strip() for v in (row.get("penalties") or []) if str(v).strip()]
        referenced_by = [_normalize_article_id(str(v)) for v in (row.get("referenced_by") or [])]
        referenced_by = [v for v in referenced_by if v]
        requirements = [str(v).strip() for v in (row.get("requirements") or []) if str(v).strip()]
        out[article_id] = {
            "obligations": _dedupe_list(obligations),
            "penalties": _dedupe_list(penalties),
            "referenced_by": _dedupe_list(referenced_by),
            "requirements": _dedupe_list(requirements),
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
                "articles": _dedupe_list(
                    [_normalize_article_id(str(v)) for v in (row.get("articles") or []) if str(v).strip()]
                ),
                "enforced_by": _dedupe_list([str(v).strip() for v in (row.get("enforced_by") or []) if str(v).strip()]),
            }
        )
    return out


def _query_usecases_by_keywords(graph: Any, keywords: Sequence[str], limit: int = 4) -> List[Dict[str, Any]]:
    kws = [str(k).strip().lower() for k in keywords if str(k).strip()]
    if not kws:
        return []
    rows = graph.query(
        """
        MATCH (u:UseCase)
        OPTIONAL MATCH (u)-[:CLASSIFIED_AS]->(r:Riskcategory)
        OPTIONAL MATCH (u)-[:REFERENCES]->(a:Article)
        WITH u,
             collect(DISTINCT r.id) AS risk_categories,
             collect(DISTINCT a.id) AS related_articles,
             toLower(coalesce(u.id,'')) AS usecase_id_l,
             toLower(coalesce(u.title,'')) AS title_l,
             toLower(coalesce(u.annex_point,'')) AS annex_l
        WITH u, risk_categories, related_articles,
             reduce(score = 0, kw IN $keywords |
                score +
                CASE WHEN title_l CONTAINS kw THEN 3 ELSE 0 END +
                CASE WHEN usecase_id_l CONTAINS kw THEN 2 ELSE 0 END +
                CASE WHEN annex_l CONTAINS kw THEN 1 ELSE 0 END
             ) AS score
        WHERE score > 0
        RETURN u.id AS usecase_id,
               coalesce(u.title,'') AS title,
               coalesce(u.annex_point,'') AS annex_point,
               risk_categories[0..4] AS risk_categories,
               related_articles[0..12] AS related_articles,
               score
        ORDER BY score DESC, usecase_id ASC
        LIMIT $limit
        """,
        {"keywords": kws, "limit": int(limit)},
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        usecase_id = str(row.get("usecase_id", "")).strip()
        if not usecase_id:
            continue
        related_articles = _dedupe_list(
            [
                _normalize_article_id(str(v))
                for v in (row.get("related_articles") or [])
                if str(v).strip()
            ]
        )
        related_articles = [v for v in related_articles if v]
        out.append(
            {
                "usecase_id": usecase_id,
                "title": str(row.get("title", "")).strip(),
                "annex_point": str(row.get("annex_point", "")).strip(),
                "risk_categories": _dedupe_list([str(v).strip() for v in (row.get("risk_categories") or []) if str(v).strip()]),
                "related_articles": related_articles,
                "score": int(row.get("score", 0) or 0),
            }
        )
    return out


def _query_timeline_by_articles(graph: Any, article_ids: Sequence[str], limit: int = 4) -> List[Dict[str, Any]]:
    normalized = _dedupe_list([_normalize_article_id(str(v)) for v in article_ids if str(v).strip()])
    normalized = [v for v in normalized if v]
    if not normalized:
        return []
    rows = graph.query(
        """
        MATCH (t:Timeline)-[:IMPLEMENTS]->(a:Article)
        WHERE a.id IN $article_ids
        RETURN coalesce(t.date_text,'') AS date_text,
               count(DISTINCT a) AS matched_article_count,
               collect(DISTINCT a.id)[0..8] AS related_articles
        ORDER BY matched_article_count DESC, date_text ASC
        LIMIT $limit
        """,
        {"article_ids": normalized, "limit": int(limit)},
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        date_text = str(row.get("date_text", "")).strip()
        if not date_text:
            continue
        rel_articles = _dedupe_list(
            [_normalize_article_id(str(v)) for v in (row.get("related_articles") or []) if str(v).strip()]
        )
        rel_articles = [v for v in rel_articles if v]
        out.append(
            {
                "date_text": date_text,
                "matched_article_count": int(row.get("matched_article_count", 0) or 0),
                "related_articles": rel_articles,
            }
        )
    return out


def _summarize_usecase_hints(usecases: Sequence[Mapping[str, Any]], max_items: int = 2) -> List[str]:
    out: List[str] = []
    for item in list(usecases)[: max(1, int(max_items))]:
        usecase_id = str(item.get("usecase_id", "")).strip()
        title = str(item.get("title", "")).strip()
        annex = str(item.get("annex_point", "")).strip()
        if usecase_id and title and annex:
            out.append(f"{usecase_id}({title}, Annex {annex})")
        elif usecase_id and title:
            out.append(f"{usecase_id}({title})")
        elif usecase_id:
            out.append(usecase_id)
    return _dedupe_list(out)


def _summarize_timeline_hints(timelines: Sequence[Mapping[str, Any]], max_items: int = 2) -> List[str]:
    out: List[str] = []
    for item in list(timelines)[: max(1, int(max_items))]:
        date_text = str(item.get("date_text", "")).strip()
        matched = int(item.get("matched_article_count", 0) or 0)
        if not date_text:
            continue
        if matched > 0:
            out.append(f"{date_text} (연결 조항 {matched}개)")
        else:
            out.append(date_text)
    return _dedupe_list(out)


def _build_kg_paths(
    *,
    related_articles: Sequence[str],
    article_context: Mapping[str, Mapping[str, List[str]]],
    requirement_evidence: Sequence[Mapping[str, Any]],
    obligation_evidence: Sequence[Mapping[str, Any]],
    max_paths: int = 12,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()

    def add(
        *,
        path_type: str,
        path_text: str,
        article_id: str = "",
        source_article_id: str = "",
        obligation_id: str = "",
        penalty_id: str = "",
        institution_id: str = "",
    ) -> None:
        key = path_text.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        out.append(
            {
                "path_type": path_type,
                "path_text": path_text,
                "article_id": article_id,
                "source_article_id": source_article_id,
                "obligation_id": obligation_id,
                "penalty_id": penalty_id,
                "institution_id": institution_id,
            }
        )

    rel_articles = _dedupe_list([_normalize_article_id(v) for v in related_articles if str(v).strip()])
    rel_articles = [v for v in rel_articles if v]

    for ob in obligation_evidence:
        obligation_id = str(ob.get("obligation_id", "")).strip()
        ob_articles = [_normalize_article_id(str(v)) for v in (ob.get("articles") or [])]
        ob_articles = [v for v in _dedupe_list(ob_articles) if v and (not rel_articles or v in rel_articles)]
        institutions = _dedupe_list([str(v).strip() for v in (ob.get("enforced_by") or []) if str(v).strip()])
        for article_id in ob_articles:
            add(
                path_type="obligation_article",
                path_text=f"(Obligation:{obligation_id}) -[DEFINED_IN]-> (Article:{article_id})",
                article_id=article_id,
                obligation_id=obligation_id,
            )
            for institution in institutions[:2]:
                add(
                    path_type="obligation_enforcement",
                    path_text=f"(Obligation:{obligation_id}) -[ENFORCED_BY]-> (Institution:{institution})",
                    article_id=article_id,
                    obligation_id=obligation_id,
                    institution_id=institution,
                )

    req_by_article: Dict[str, List[str]] = {}
    for item in requirement_evidence:
        article_id = _normalize_article_id(str(item.get("article_id", "")))
        req_text = str(item.get("req_text", "")).strip()
        if not article_id or not req_text:
            continue
        req_by_article.setdefault(article_id, []).append(req_text)
    for article_id in list(req_by_article.keys()):
        req_by_article[article_id] = _dedupe_list(req_by_article[article_id])

    for article_id in rel_articles:
        ctx = article_context.get(article_id, {})
        req_candidates = req_by_article.get(article_id, []) or (ctx.get("requirements") or [])
        for req in req_candidates[:2]:
            req_label = _summarize_requirement_ko(str(req))
            add(
                path_type="article_requirement",
                path_text=f"(ComplianceReq:{req_label}) -[DEFINED_IN]-> (Article:{article_id})",
                article_id=article_id,
            )
        for penalty in (ctx.get("penalties") or [])[:2]:
            add(
                path_type="article_penalty",
                path_text=f"(Article:{article_id}) -[IMPOSES]-> (Penalty:{_clip(str(penalty), 80)})",
                article_id=article_id,
                penalty_id=str(penalty),
            )
        for src in (ctx.get("referenced_by") or [])[:2]:
            add(
                path_type="article_reference",
                path_text=f"(Article:{src}) -[REFERENCES]-> (Article:{article_id})",
                article_id=article_id,
                source_article_id=src,
            )

    return out[: max(1, int(max_paths))]


def _has_article_evidence(context: Mapping[str, List[str]] | None) -> bool:
    if not context:
        return False
    return bool(
        (context.get("obligations") or [])
        or (context.get("penalties") or [])
        or (context.get("requirements") or [])
        or (context.get("referenced_by") or [])
    )


def _build_grounded_finding(
    *,
    theme: str,
    trigger_terms: Sequence[str],
    related_articles: Sequence[str],
    requirement_evidence: Sequence[Mapping[str, Any]],
    obligation_evidence: Sequence[Mapping[str, Any]],
    evidence_status: str = "grounded",
    expected_labels: Sequence[str] | None = None,
    matched_labels: Sequence[str] | None = None,
    friendly_text: bool = True,
) -> str:
    safe_theme = _normalize_theme(theme)
    articles = [str(v).strip() for v in related_articles if str(v).strip()]
    signal_hint = _render_signal_hint(trigger_terms)
    expected_labels = [str(v).strip() for v in (expected_labels or []) if str(v).strip()]
    matched_labels = [str(v).strip() for v in (matched_labels or []) if str(v).strip()]

    if evidence_status == "mismatch_downgraded":
        controls = ", ".join(expected_labels[:2]) if expected_labels else "핵심 통제"
        article_hint = _render_article_refs(articles, max_items=3, include_brief=friendly_text)
        return (
            f"{signal_hint}'{safe_theme}' 정황은 감지됐지만, "
            "현재 근거와 설명의 직접 일치도가 낮아 예비 경고로 자동 강등했습니다. "
            f"{article_hint} 기준으로 {controls} 항목부터 사실관계를 보강해 재진단하세요."
        )

    if requirement_evidence:
        labels = matched_labels or _dedupe_list(
            [
                _summarize_requirement_ko(str(item.get("req_text", "")), str(item.get("req_id", "")))
                for item in requirement_evidence[:3]
            ]
        )
        labels = [v for v in labels if v]
        article_hint = _render_article_refs(
            _dedupe_list([str(item.get("article_id", "")).strip() for item in requirement_evidence[:3]])[:3],
            max_items=3,
            include_brief=friendly_text,
        )
        if labels:
            return (
                f"{signal_hint}'{safe_theme}' 위험이 있습니다. "
                f"{article_hint or _render_article_refs(articles, max_items=3, include_brief=friendly_text)} 기준으로 "
                f"{', '.join(labels[:2])}이 확인되었습니다."
            )
    if obligation_evidence:
        snippets = [
            _summarize_requirement_ko(
                str(item.get("description", "")).strip() or str(item.get("obligation_id", "")).strip(),
                str(item.get("obligation_id", "")).strip(),
            )
            for item in obligation_evidence[:2]
        ]
        snippets = [s for s in snippets if s]
        if snippets:
            joined = _render_article_refs(articles, max_items=3, include_brief=friendly_text)
            return (
                f"{signal_hint}'{safe_theme}' 위험이 있습니다. "
                f"{joined} 기준 의무로 {', '.join(snippets[:2])}이 확인되었습니다."
            )
    if articles:
        return (
            f"{signal_hint}'{safe_theme}' 관련 조항은 확인됐지만 "
            f"직접 연결된 세부 요건은 제한적입니다 (관련 조항: {_render_article_refs(articles, max_items=4, include_brief=friendly_text)})."
        )
    return (
        f"{signal_hint}'{safe_theme}' 이슈는 충분한 조항 근거를 찾지 못했습니다. "
        "현재 결과는 예비 진단으로 보고, 사실관계를 보강한 뒤 재진단하세요."
    )


def _build_grounded_action(
    *,
    theme: str,
    related_articles: Sequence[str],
    requirement_evidence: Sequence[Mapping[str, Any]],
    obligation_evidence: Sequence[Mapping[str, Any]],
    evidence_status: str = "grounded",
    expected_labels: Sequence[str] | None = None,
    friendly_text: bool = True,
) -> str:
    safe_theme = _normalize_theme(theme)
    articles = [str(v).strip() for v in related_articles if str(v).strip()]
    expected_labels = [str(v).strip() for v in (expected_labels or []) if str(v).strip()]

    if evidence_status == "insufficient":
        return (
            f"'{safe_theme}'은 현재 근거가 부족한 예비 진단입니다. "
            "대상 데이터, 처리 목적, 배포 범위, 실제 운영 절차를 보강한 뒤 재진단하세요."
        )

    if evidence_status == "mismatch_downgraded":
        primary = expected_labels[0] if expected_labels else "핵심 통제 요건"
        return (
            f"'{safe_theme}'은 근거-설명 정합성이 낮아 예비 경고로 자동 강등되었습니다. "
            f"{primary} 중심으로 사실관계(대상 데이터, 처리 목적, 배포 범위)를 보강한 뒤 재진단하세요. "
            f"{_action_hint_from_label(primary)}"
        )

    if requirement_evidence:
        first = requirement_evidence[0]
        article = str(first.get("article_id", "")).strip()
        req_label = _summarize_requirement_ko(str(first.get("req_text", "")).strip(), str(first.get("req_id", "")).strip())
        action_hint = _action_hint_from_label(req_label)
        if article and req_label:
            article_ref = _render_article_refs([article], max_items=1, include_brief=friendly_text)
            return f"'{safe_theme}' 대응으로 {article_ref}의 '{req_label}'을 우선 적용하세요. {action_hint}"
    if obligation_evidence:
        first = obligation_evidence[0]
        label = _summarize_requirement_ko(
            str(first.get("description", "")).strip() or str(first.get("obligation_id", "")).strip(),
            str(first.get("obligation_id", "")).strip(),
        )
        if label:
            base = _render_article_refs(articles, max_items=3, include_brief=friendly_text) if articles else "관련 AI Act 조항"
            return f"'{safe_theme}' 대응으로 {base} 기준 '{label}' 통제를 우선 이행하세요. {_action_hint_from_label(label)}"
    if articles:
        return (
            f"'{safe_theme}' 대응으로 {_render_article_refs(articles, max_items=3, include_brief=friendly_text)} 기준 통제를 우선 정리하세요. "
            "문서화, 로그/추적성, 투명성, 데이터 거버넌스 항목부터 반영하면 됩니다."
        )
    return "근거가 충분하지 않습니다. 시나리오 사실관계를 보강한 뒤 리트리버를 다시 실행하세요."


def _friendly_primary_controls(
    *,
    requirement_evidence: Sequence[Mapping[str, Any]],
    obligation_evidence: Sequence[Mapping[str, Any]],
    max_items: int = 3,
) -> List[str]:
    controls: List[str] = []
    for item in requirement_evidence[: max(1, int(max_items) + 2)]:
        label = _summarize_requirement_ko(str(item.get("req_text", "")), str(item.get("req_id", "")))
        if label:
            controls.append(label)
    for item in obligation_evidence[:2]:
        label = _summarize_requirement_ko(
            str(item.get("description", "")).strip() or str(item.get("obligation_id", "")).strip(),
            str(item.get("obligation_id", "")).strip(),
        )
        if label:
            controls.append(label)
    return _dedupe_list(controls)[: max(1, int(max_items))]


def _friendly_supporting_paths_preview(
    *,
    kg_paths: Sequence[Mapping[str, Any]],
    max_items: int = 3,
) -> List[str]:
    lines: List[str] = []
    for path in kg_paths[: max(1, int(max_items) + 2)]:
        if not isinstance(path, Mapping):
            continue
        path_type = str(path.get("path_type", "")).strip().lower()
        article_id = _normalize_article_id(str(path.get("article_id", "")).strip())
        source_article_id = _normalize_article_id(str(path.get("source_article_id", "")).strip())
        obligation_id = str(path.get("obligation_id", "")).strip()
        if path_type == "obligation_article" and obligation_id and article_id:
            lines.append(f"의무 항목 {obligation_id}이 {article_id}와 직접 연결됨")
        elif path_type == "article_reference" and source_article_id and article_id:
            lines.append(f"{source_article_id}이 {article_id}를 참조함")
        elif path_type in {"article_penalty", "obligation_article_penalty"} and article_id:
            lines.append(f"{article_id}와 제재/책임 경로가 연결됨")
    return _dedupe_list(lines)[: max(1, int(max_items))]


def _build_user_evidence_bullets(
    *,
    theme: str,
    trigger_terms: Sequence[str],
    related_articles: Sequence[str],
    requirement_evidence: Sequence[Mapping[str, Any]],
    obligation_evidence: Sequence[Mapping[str, Any]],
    evidence_status: str,
    evidence_confidence: float,
    kg_paths: Sequence[Mapping[str, Any]],
) -> List[str]:
    bullets: List[str] = []
    safe_theme = _normalize_theme(theme)
    compact_terms = [str(v).strip() for v in trigger_terms if str(v).strip()][:3]
    if compact_terms:
        bullets.append(f"문서에서 '{', '.join(compact_terms)}' 정황이 확인되어 '{safe_theme}' 이슈로 분류했습니다.")

    article_lines = _article_brief_lines(related_articles, max_items=3)
    if article_lines:
        bullets.append(f"관련 조항 요약: {' / '.join(article_lines)}")

    controls = _friendly_primary_controls(
        requirement_evidence=requirement_evidence,
        obligation_evidence=obligation_evidence,
        max_items=2,
    )
    if controls:
        bullets.append(f"핵심 의무 포인트: {', '.join(controls)}")

    path_lines = _friendly_supporting_paths_preview(kg_paths=kg_paths, max_items=2)
    if path_lines:
        bullets.append(f"추가 연결 근거: {' / '.join(path_lines)}")

    confidence_pct = max(0, min(100, int(round(float(evidence_confidence or 0.0) * 100))))
    status_map = {
        "grounded": "근거 확인",
        "mismatch_downgraded": "정합성 낮음(자동 강등)",
        "insufficient": "근거 부족(예비 진단)",
    }
    status_text = status_map.get(str(evidence_status or "").strip().lower(), "근거 상태 미확인")
    bullets.append(f"근거 상태: {status_text} / 근거 신뢰도(내부): {confidence_pct}%")
    return _dedupe_list([str(v).strip() for v in bullets if str(v).strip()])[:6]


def _llm_issue_extraction(
    *,
    customer_text: str,
    user_question: str | None,
    model_name: str,
) -> Dict[str, Any]:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=model_name, temperature=0)
    question = str(user_question or "").strip()
    prompt = (
        "You are an intent parser for EU AI Act scenario analysis.\n"
        "Given user question and customer text, extract only risk signals for retrieval.\n"
        "Return strict JSON only with this schema:\n"
        "{\n"
        '  "issues":[{\n'
        '    "theme":"string",\n'
        '    "severity":"high|medium|low",\n'
        '    "risk_points":0,\n'
        '    "trigger_terms":["string"],\n'
        '    "retrieval_keywords":["string"]\n'
        "  }]\n"
        "}\n"
        "Constraints:\n"
        "- Max 6 issues.\n"
        "- Use concrete themes tied to user context.\n"
        "- retrieval_keywords must be short lowercase English phrases.\n"
        "- Do not output legal conclusions.\n"
        "- Do not mention non-AI-Act laws (e.g., GDPR, CCPA).\n"
        "- Do not output article numbers.\n"
        "\n"
        f"[Question]\n{question}\n\n"
        f"[CustomerText]\n{customer_text}\n"
    )
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response))
    payload = _extract_json_payload(str(content))
    return payload if isinstance(payload, dict) else {}


def _build_summary_from_issues(
    issues: Sequence[Mapping[str, Any]],
    *,
    legal_state: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    actionable = [
        item
        for item in issues
        if str(item.get("evidence_status", "")).strip() in {"grounded", "mismatch_downgraded"}
        and int(item.get("risk_points", 0) or 0) > 0
    ]
    score = min(100, sum(int(item.get("risk_points", 0) or 0) for item in actionable))
    high_count = sum(1 for item in actionable if str(item.get("severity", "")).lower() == "high")
    medium_count = sum(1 for item in actionable if str(item.get("severity", "")).lower() == "medium")
    low_count = sum(1 for item in actionable if str(item.get("severity", "")).lower() == "low")
    if high_count >= 1:
        score = max(score, 40)
    elif medium_count >= 2:
        score = max(score, 30)
    elif medium_count == 1:
        score = max(score, 20)

    prohibited_confirmed = any(
        (
            "Article 5" in [str(v).strip() for v in (item.get("related_articles") or [])]
            and str(item.get("evidence_status", "")).strip() in {"grounded", "mismatch_downgraded"}
        )
        for item in issues
    )
    high_risk_confirmed = any(
        (
            "Article 6" in [str(v).strip() for v in (item.get("related_articles") or [])]
            and str(item.get("evidence_status", "")).strip() in {"grounded", "mismatch_downgraded"}
        )
        for item in issues
    )
    if prohibited_confirmed:
        score = max(score, 75)
    elif high_risk_confirmed:
        score = max(score, 55)

    if score >= 70:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"
    grounded_count = sum(1 for item in issues if str(item.get("evidence_status", "")).strip() == "grounded")
    mismatch_count = sum(1 for item in issues if str(item.get("evidence_status", "")).strip() == "mismatch_downgraded")
    insufficient_count = sum(1 for item in issues if str(item.get("evidence_status", "")).strip() == "insufficient")
    return {
        "risk_level": level,
        "risk_score": int(score),
        "issue_count": len(issues),
        "actionable_issue_count": len(actionable),
        "grounded_issue_count": int(grounded_count),
        "mismatch_downgraded_issue_count": int(mismatch_count),
        "insufficient_issue_count": int(insufficient_count),
        "preliminary_issue_count": int(insufficient_count),
        "high_issue_count": int(high_count),
        "medium_issue_count": int(medium_count),
        "low_issue_count": int(low_count),
        "prohibited_confirmed": bool(prohibited_confirmed),
        "high_risk_confirmed": bool(high_risk_confirmed),
        "legal_state": dict(legal_state or {}),
    }


def run_intent_rag_assessment(
    *,
    graph: Any,
    customer_text: str,
    user_question: str | None,
    model_name: str,
    top_k_usecases: int = 3,
    retriever_mode: str = "v2",
    retriever_shadow: bool = False,
    retriever_profile: str = "precision_first",
    friendly_text: bool = True,
    article_diversity: bool = True,
    extended_kg: bool = True,
) -> Dict[str, Any]:
    """Run LLM intent parsing + KG retrieval + grounded response generation."""
    question = str(user_question or "").strip()
    body = str(customer_text or "").strip()
    mode = str(retriever_mode or "v2").strip().lower()
    if mode not in {"v1", "v2"}:
        mode = "v2"
    profile = str(retriever_profile or "precision_first").strip().lower() or "precision_first"
    shadow_enabled = bool(retriever_shadow)
    rule_issues = _extract_rule_based_issue_signals(customer_text=body, user_question=question)
    llm_raw_issues: List[Mapping[str, Any]] = []
    llm_extraction_failed = False
    try:
        extracted = _llm_issue_extraction(customer_text=body, user_question=question, model_name=model_name)
        candidate = extracted.get("issues", []) if isinstance(extracted, dict) else []
        if isinstance(candidate, list):
            llm_raw_issues = [v for v in candidate if isinstance(v, Mapping)]
        if not llm_raw_issues:
            raise ValueError("No issues extracted from LLM.")
    except Exception:
        llm_extraction_failed = True
        llm_raw_issues = []

    raw_issues = _merge_hybrid_extracted_issues(
        llm_issues=llm_raw_issues,
        rule_issues=rule_issues,
        max_items=6,
    )
    legal_state = _classify_legal_state(customer_text=body, user_question=question)
    legal_state_required_articles = [
        str(v).strip() for v in (legal_state.get("required_articles") or []) if str(v).strip()
    ]
    legal_state_required_clauses = [
        str(v).strip() for v in (legal_state.get("required_clauses") or []) if str(v).strip()
    ]

    if not raw_issues:
        fallback = run_intent_scenario_assessment(
            graph=graph,
            customer_text=body,
            user_question=question,
            top_k_usecases=top_k_usecases,
        )
        fallback_meta = fallback.get("meta", {})
        if isinstance(fallback_meta, dict):
            fallback_meta["engine"] = "intent_rag_diagnoser_fallback_rule_v1"
            fallback_meta["fallback_reason"] = "llm_extraction_failed_or_empty"
            fallback_meta["retriever_version"] = "intent_retriever_v1"
            fallback_meta["retriever_profile"] = profile
            fallback_meta["retriever_shadow_enabled"] = shadow_enabled
            fallback_meta["retrieval_debug"] = {"mode": mode, "fallback": True}
            fallback_meta["llm_extraction_failed"] = True
            fallback_meta["rule_signal_count"] = len(rule_issues)
            fallback_meta["legal_state"] = dict(legal_state or {})
            fallback["meta"] = fallback_meta
        return fallback

    normalized_issues: List[Dict[str, Any]] = []
    retrieval_debug_rows: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_issues[:6], start=1):
        if not isinstance(item, Mapping):
            continue
        severity = str(item.get("severity", "medium")).strip().lower()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        risk_points = int(item.get("risk_points", 0) or 0)
        min_points = DEFAULT_RISK_POINTS[severity]
        if risk_points < min_points:
            risk_points = min_points

        theme = _normalize_theme(str(item.get("theme", "Scenario risk")).strip() or "Scenario risk")
        retrieval_keywords = _dedupe_list(
            [str(v).strip().lower() for v in (item.get("retrieval_keywords") or []) if str(v).strip()]
        )
        trigger_terms = _dedupe_list([str(v).strip() for v in (item.get("trigger_terms") or []) if str(v).strip()])
        effective_keywords = _expand_retrieval_keywords(
            theme=theme,
            retrieval_keywords=retrieval_keywords,
            trigger_terms=trigger_terms,
        )

        # Do not trust LLM-proposed articles. Build candidates from retrieval only.
        hint_articles = _keyword_article_candidates(effective_keywords + trigger_terms)
        query_articles = _query_articles_by_keywords(graph=graph, keywords=effective_keywords + trigger_terms, limit=20)
        if extended_kg:
            usecase_candidates: List[Dict[str, Any]] = _query_usecases_by_keywords(
                graph=graph,
                keywords=[theme] + effective_keywords + trigger_terms,
                limit=4,
            )
        else:
            usecase_candidates = []
        usecase_articles = _dedupe_list(
            [
                str(v).strip()
                for candidate in usecase_candidates
                for v in (candidate.get("related_articles") or [])
                if str(v).strip()
            ]
        )
        mandatory_articles = _derive_mandatory_articles(
            theme=theme,
            retrieval_keywords=effective_keywords,
            trigger_terms=trigger_terms,
            legal_state_required_articles=legal_state_required_articles,
            hint_articles=hint_articles,
            query_articles=query_articles,
            usecase_candidates=usecase_candidates,
        )
        requirement_hits: List[Dict[str, Any]] = []
        obligation_hits: List[Dict[str, Any]] = []
        retrieval_trace: List[Dict[str, Any]] = []
        issue_retrieval_debug: Dict[str, Any] = {}
        evidence_confidence = 0.0
        primary_evidence_type = "requirement"

        if mode == "v2":
            expected_codes = _expected_control_codes(
                theme=theme,
                retrieval_keywords=effective_keywords,
                trigger_terms=trigger_terms,
            )
            v2_result = retrieve_issue_evidence_v2(
                graph=graph,
                theme=theme,
                trigger_terms=trigger_terms,
                retrieval_keywords=effective_keywords,
                expected_control_codes=expected_codes,
                summarize_requirement_ko=_summarize_requirement_ko,
                control_code_from_label=_control_code_from_label,
                is_noisy_requirement=_is_noisy_requirement,
                mandatory_articles=mandatory_articles,
            )
            requirement_hits = [
                dict(v) for v in (v2_result.get("requirement_evidence") or []) if isinstance(v, Mapping)
            ]
            obligation_hits = [
                dict(v) for v in (v2_result.get("obligation_evidence") or []) if isinstance(v, Mapping)
            ]
            retrieval_trace = [
                dict(v) for v in (v2_result.get("retrieval_trace") or []) if isinstance(v, Mapping)
            ]
            issue_retrieval_debug = dict(v2_result.get("retrieval_debug") or {})
            evidence_confidence = float(v2_result.get("evidence_confidence", 0.0) or 0.0)
            primary_evidence_type = str(v2_result.get("primary_evidence_type", "requirement")).strip() or "requirement"
            req_articles = _dedupe_list([str(item.get("article_id", "")).strip() for item in requirement_hits])
            ob_articles = _dedupe_list(
                [str(v).strip() for item in obligation_hits for v in (item.get("articles") or []) if str(v).strip()]
            )
            v2_related = _dedupe_list(
                [str(v).strip() for v in (v2_result.get("related_articles") or []) if str(v).strip()]
            )
            # precision-first: use v2 accepted evidence only
            all_related_articles = _dedupe_list(req_articles + ob_articles + v2_related)
        else:
            requirement_raw = _query_requirements_by_keywords(
                graph=graph, keywords=effective_keywords + trigger_terms, limit=64
            )
            requirement_hits = _rank_requirement_evidence(
                requirements=requirement_raw,
                focus_keywords=[theme] + effective_keywords + trigger_terms,
                preferred_articles=hint_articles + query_articles,
                max_items=8,
            )
            req_articles = _dedupe_list([str(item.get("article_id", "")).strip() for item in requirement_hits])
            all_related_articles = _dedupe_list(hint_articles + query_articles + req_articles)
            evidence_confidence = 0.0
            primary_evidence_type = "requirement"
            issue_retrieval_debug = {
                "channel_hits": {
                    "lexical_requirements": len(requirement_hits),
                    "lexical_obligations": 0,
                    "lexical_articles": len(query_articles),
                    "graph_path_articles": 0,
                },
                "selected_counts": {
                    "requirements": len(requirement_hits),
                    "obligations": 0,
                    "related_articles": len(all_related_articles),
                },
                "thresholds": {"final_threshold": 0.0, "low_alignment_path_floor": 0.30},
            }
        all_related_articles = _dedupe_list(all_related_articles + usecase_articles)
        all_related_articles = _apply_article_diversity(
            theme=theme,
            article_ids=all_related_articles,
            enabled=bool(article_diversity),
        )
        all_related_articles = _cap_related_articles(
            article_ids=all_related_articles,
            mandatory_articles=mandatory_articles,
            max_items=4,
        )
        channel_hits = issue_retrieval_debug.get("channel_hits", {}) if isinstance(issue_retrieval_debug, Mapping) else {}
        if isinstance(channel_hits, Mapping):
            issue_retrieval_debug = dict(issue_retrieval_debug)
            issue_retrieval_debug["channel_hits"] = {**dict(channel_hits), "usecases": int(len(usecase_candidates))}

        normalized_issues.append(
            {
                "issue_id": f"RAG-{idx:02d}",
                "theme": theme,
                "severity": severity,
                "risk_points": int(risk_points),
                "trigger_terms": trigger_terms,
                "retrieval_keywords": effective_keywords,
                "related_articles": all_related_articles,
                "requirement_candidates": requirement_hits,
                "obligation_candidates": obligation_hits,
                "retrieval_trace": retrieval_trace,
                "retrieval_debug": issue_retrieval_debug,
                "evidence_confidence": float(evidence_confidence),
                "primary_evidence_type": primary_evidence_type,
                "usecase_candidates": usecase_candidates,
                "mandatory_articles": mandatory_articles,
                "required_clauses": legal_state_required_clauses,
                "usecase_hints": _summarize_usecase_hints(usecase_candidates, max_items=3),
            }
        )
        retrieval_debug_rows.append(issue_retrieval_debug)

    normalized_issues = _dedupe_overlapping_issue_signals(normalized_issues, max_items=6)
    for idx, item in enumerate(normalized_issues, start=1):
        item["issue_id"] = f"RAG-{idx:02d}"
        item["theme"] = _normalize_theme(str(item.get("theme", "")))

    all_articles: List[str] = []
    for item in normalized_issues:
        all_articles.extend(item.get("related_articles", []))
        all_articles.extend(item.get("mandatory_articles", []))
    article_context = _query_article_context(graph=graph, article_ids=_dedupe_list(all_articles))

    enriched_issues: List[Dict[str, Any]] = []
    for item in normalized_issues:
        related_articles = [str(v).strip() for v in (item.get("related_articles") or []) if str(v).strip()]
        mandatory_articles = [str(v).strip() for v in (item.get("mandatory_articles") or []) if str(v).strip()]
        if mode == "v2":
            obligation_evidence = [
                dict(v) for v in (item.get("obligation_candidates") or []) if isinstance(v, Mapping)
            ]
        else:
            obligation_evidence = _query_obligations_by_keywords(
                graph=graph,
                keywords=item.get("retrieval_keywords", []) + item.get("trigger_terms", []),
                limit=8,
            )
        requirement_evidence = [dict(v) for v in (item.get("requirement_candidates") or []) if isinstance(v, Mapping)]
        if not requirement_evidence and mode != "v2":
            requirement_fallback = _query_requirements_by_keywords(
                graph=graph,
                keywords=item.get("retrieval_keywords", []) + item.get("trigger_terms", []),
                limit=64,
            )
            requirement_evidence = _rank_requirement_evidence(
                requirements=requirement_fallback,
                focus_keywords=[str(item.get("theme", ""))] + list(item.get("retrieval_keywords", [])) + list(item.get("trigger_terms", [])),
                preferred_articles=related_articles,
                max_items=8,
            )
        if not obligation_evidence and mode != "v2":
            obligation_evidence = _query_obligations_by_keywords(
                graph=graph,
                keywords=item.get("retrieval_keywords", []) + item.get("trigger_terms", []),
                limit=8,
            )
        requirement_evidence = _prioritize_requirements_for_theme(
            theme=str(item.get("theme", "")),
            requirement_evidence=requirement_evidence,
        )
        primary_requirement = _select_primary_requirement_for_theme(
            theme=str(item.get("theme", "")),
            requirement_evidence=requirement_evidence,
        )
        if primary_requirement:
            remainder = [
                dict(v)
                for v in requirement_evidence
                if str(v.get("req_id", "")).strip() != str(primary_requirement.get("req_id", "")).strip()
            ]
            requirement_evidence = [dict(primary_requirement)] + remainder
        requirement_articles = _dedupe_list([str(ev.get("article_id", "")).strip() for ev in requirement_evidence])
        merged_articles = _dedupe_list(related_articles + requirement_articles)
        supported_articles = [article_id for article_id in merged_articles if _has_article_evidence(article_context.get(article_id))]
        if not supported_articles:
            supported_articles = requirement_articles[:]
        if not supported_articles and mandatory_articles:
            mandatory_supported = [
                article_id
                for article_id in _dedupe_list(mandatory_articles)
                if _has_article_evidence(article_context.get(article_id))
            ]
            if mandatory_supported:
                supported_articles = mandatory_supported[:]
            else:
                supported_articles = _dedupe_list(mandatory_articles)[:3]
        timeline_evidence = _query_timeline_by_articles(graph=graph, article_ids=supported_articles, limit=4) if extended_kg else []
        timeline_hints = _summarize_timeline_hints(timeline_evidence, max_items=2) if extended_kg else []
        supported_articles = _apply_article_diversity(
            theme=str(item.get("theme", "")),
            article_ids=supported_articles,
            enabled=bool(article_diversity),
        )
        supported_articles = _cap_related_articles(
            article_ids=supported_articles,
            mandatory_articles=mandatory_articles,
            max_items=4,
        )
        alignment = _evaluate_evidence_alignment(
            theme=str(item.get("theme", "")),
            retrieval_keywords=list(item.get("retrieval_keywords", [])),
            trigger_terms=list(item.get("trigger_terms", [])),
            requirement_evidence=requirement_evidence,
            obligation_evidence=obligation_evidence,
            related_articles=supported_articles,
            mandatory_articles=mandatory_articles,
        )
        evidence_status = str(alignment.get("status", "insufficient")).strip() or "insufficient"
        original_severity = str(item.get("severity", "medium")).strip().lower()
        effective_severity = original_severity
        effective_risk_points = int(item.get("risk_points", 0) or 0)
        if evidence_status == "insufficient":
            effective_risk_points = 0
        elif evidence_status == "mismatch_downgraded":
            effective_severity = _downgrade_severity(original_severity)
            if effective_severity == "low":
                effective_risk_points = min(effective_risk_points, max(4, DEFAULT_RISK_POINTS["low"] // 2))
            else:
                effective_risk_points = min(effective_risk_points, DEFAULT_RISK_POINTS[effective_severity])
            if effective_risk_points <= 0:
                effective_risk_points = 4 if effective_severity == "low" else DEFAULT_RISK_POINTS[effective_severity]
        grounded = evidence_status in {"grounded", "mismatch_downgraded"}

        kg_article_evidence = []
        for article_id in supported_articles:
            ctx = article_context.get(article_id, {})
            kg_article_evidence.append(
                {
                    "article_id": article_id,
                    "obligations": ctx.get("obligations", []),
                    "penalties": ctx.get("penalties", []),
                    "referenced_by": ctx.get("referenced_by", []),
                    "requirements": ctx.get("requirements", []),
                }
            )

        kg_paths = _build_kg_paths(
            related_articles=supported_articles,
            article_context=article_context,
            requirement_evidence=requirement_evidence,
            obligation_evidence=obligation_evidence,
            max_paths=12,
        )
        finding = _build_grounded_finding(
            theme=str(item.get("theme", "")),
            trigger_terms=item.get("trigger_terms", []),
            related_articles=supported_articles,
            requirement_evidence=requirement_evidence,
            obligation_evidence=obligation_evidence,
            evidence_status=evidence_status,
            expected_labels=list(alignment.get("expected_labels", [])),
            matched_labels=list(alignment.get("matched_labels", [])),
            friendly_text=bool(friendly_text),
        )
        recommended_action = _build_grounded_action(
            theme=str(item.get("theme", "")),
            related_articles=supported_articles,
            requirement_evidence=requirement_evidence,
            obligation_evidence=obligation_evidence,
            evidence_status=evidence_status,
            expected_labels=list(alignment.get("expected_labels", [])),
            friendly_text=bool(friendly_text),
        )
        primary_controls = _friendly_primary_controls(
            requirement_evidence=requirement_evidence,
            obligation_evidence=obligation_evidence,
            max_items=3,
        )
        supporting_paths_preview = _friendly_supporting_paths_preview(kg_paths=kg_paths, max_items=3)
        evidence_bullets = _build_user_evidence_bullets(
            theme=str(item.get("theme", "")),
            trigger_terms=item.get("trigger_terms", []),
            related_articles=supported_articles,
            requirement_evidence=requirement_evidence,
            obligation_evidence=obligation_evidence,
            evidence_status=evidence_status if grounded else "insufficient",
            evidence_confidence=float(item.get("evidence_confidence", 0.0) or 0.0),
            kg_paths=kg_paths,
        )
        primary_control_label = ""
        if requirement_evidence:
            first_req = requirement_evidence[0]
            primary_control_label = _summarize_requirement_ko(
                str(first_req.get("req_text", "")).strip(),
                str(first_req.get("req_id", "")).strip(),
            )
        if evidence_status == "mismatch_downgraded":
            expected_labels = [str(v).strip() for v in alignment.get("expected_labels", []) if str(v).strip()]
            if expected_labels:
                primary_control_label = expected_labels[0]

        enriched_issues.append(
            {
                **item,
                "original_severity": original_severity,
                "severity": effective_severity,
                "risk_points": effective_risk_points,
                "related_articles": supported_articles,
                "related_article_briefs": _article_brief_lines(supported_articles, max_items=6),
                "evidence_status": evidence_status if grounded else "insufficient",
                "evidence_confidence": float(item.get("evidence_confidence", 0.0) or 0.0),
                "primary_evidence_type": str(item.get("primary_evidence_type", "requirement") or "requirement"),
                "retrieval_trace": [dict(v) for v in (item.get("retrieval_trace") or []) if isinstance(v, Mapping)],
                "finding": finding,
                "recommended_action": recommended_action,
                "evidence_bullets": evidence_bullets,
                "primary_controls": primary_controls,
                "supporting_paths_preview": supporting_paths_preview,
                "primary_control_label": primary_control_label,
                "alignment_expected_controls": list(alignment.get("expected_labels", [])),
                "alignment_matched_controls": list(alignment.get("matched_labels", [])),
                "required_clauses": [str(v).strip() for v in (item.get("required_clauses") or []) if str(v).strip()],
                "kg_article_evidence": kg_article_evidence,
                "requirement_evidence": requirement_evidence,
                "obligation_evidence": obligation_evidence,
                "kg_paths": kg_paths,
                "usecase_hints": [str(v).strip() for v in (item.get("usecase_hints") or []) if str(v).strip()],
                "timeline_hints": timeline_hints,
                "timeline_evidence": timeline_evidence,
            }
        )

    evidence_order = {"grounded": 0, "mismatch_downgraded": 1, "insufficient": 2}
    severity_order = {"high": 0, "medium": 1, "low": 2}
    enriched_issues.sort(
        key=lambda x: (
            evidence_order.get(str(x.get("evidence_status", "insufficient")), 9),
            severity_order.get(str(x.get("severity", "low")), 9),
            -int(x.get("risk_points", 0) or 0),
        )
    )

    summary = _build_summary_from_issues(enriched_issues, legal_state=legal_state)
    key_findings = _dedupe_list(
        [str(item.get("finding", "")).strip() for item in enriched_issues[:6] if str(item.get("finding", "")).strip()]
    )
    next_actions: List[str] = []
    seen_control = set()
    for item in enriched_issues[:8]:
        if str(item.get("evidence_status", "")).strip() == "insufficient":
            continue
        action = str(item.get("recommended_action", "")).strip()
        if not action:
            continue
        control = str(item.get("primary_control_label", "")).strip().lower()
        if control and control in seen_control:
            continue
        if control:
            seen_control.add(control)
        next_actions.append(action)

    channel_totals = {
        "lexical_requirements": 0,
        "lexical_obligations": 0,
        "lexical_articles": 0,
        "graph_path_articles": 0,
        "usecases": 0,
    }
    selected_totals = {
        "requirements": 0,
        "obligations": 0,
        "related_articles": 0,
    }
    for row in retrieval_debug_rows:
        if not isinstance(row, Mapping):
            continue
        channel = row.get("channel_hits", {}) if isinstance(row.get("channel_hits", {}), Mapping) else {}
        selected = row.get("selected_counts", {}) if isinstance(row.get("selected_counts", {}), Mapping) else {}
        channel_totals["lexical_requirements"] += int(channel.get("lexical_requirements", 0) or 0)
        channel_totals["lexical_obligations"] += int(channel.get("lexical_obligations", 0) or 0)
        channel_totals["lexical_articles"] += int(channel.get("lexical_articles", 0) or 0)
        channel_totals["graph_path_articles"] += int(channel.get("graph_path_articles", 0) or 0)
        channel_totals["usecases"] += int(channel.get("usecases", 0) or 0)
        selected_totals["requirements"] += int(selected.get("requirements", 0) or 0)
        selected_totals["obligations"] += int(selected.get("obligations", 0) or 0)
        selected_totals["related_articles"] += int(selected.get("related_articles", 0) or 0)

    retrieval_debug = {
        "mode": mode,
        "profile": profile,
        "issue_count": len(normalized_issues),
        "legal_state": dict(legal_state or {}),
        "hybrid_signal": {
            "llm_issue_count": int(len(llm_raw_issues)),
            "rule_issue_count": int(len(rule_issues)),
            "llm_extraction_failed": bool(llm_extraction_failed),
        },
        "channel_hits_total": channel_totals,
        "selected_total": selected_totals,
    }

    report = {
        "meta": {
            "generated_at": _now(),
            "engine": "intent_rag_diagnoser_v2" if mode == "v2" else "intent_rag_diagnoser_v1",
            "model_name": model_name,
            "top_k_usecases": int(top_k_usecases),
            "grounding_policy": "retrieval_only_output",
            "retriever_version": "intent_retriever_v2" if mode == "v2" else "intent_retriever_v1",
            "retriever_profile": profile,
            "retriever_shadow_enabled": shadow_enabled,
            "friendly_text_enabled": bool(friendly_text),
            "article_diversity_enabled": bool(article_diversity),
            "extended_kg_enabled": bool(extended_kg),
            "hybrid_signal_enabled": True,
            "llm_issue_count": int(len(llm_raw_issues)),
            "rule_issue_count": int(len(rule_issues)),
            "llm_extraction_failed": bool(llm_extraction_failed),
            "legal_state": dict(legal_state or {}),
            "retrieval_debug": retrieval_debug,
            "shadow_diff_path": None,
        },
        "input": {
            "question": question,
            "customer_text_preview": body[:500],
            "char_count": len(body),
        },
        "summary": {
            **summary,
            "key_findings": key_findings,
            "next_actions": next_actions,
        },
        "mapping": {
            # Keep compatibility with existing consumers.
            "usecase_candidates": [],
        },
        "issues": enriched_issues,
    }
    return report

