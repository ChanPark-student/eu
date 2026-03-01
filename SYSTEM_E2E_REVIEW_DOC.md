# AI Act 기반 E2E 시스템 설명서 (검토용 단일 문서)

## 문서 목적과 읽는 법
이 문서는 외부 검토자(사람/AI)가 **추가 자료 없이** 현재 시스템의 목적, UI/UX, 아키텍처, KG 활용, 검색/생성 상호작용, 한계와 개선 방향까지 파악할 수 있도록 작성한 단일 기술 설명서다.  
문서 성격은 홍보가 아니라 **검증 가능한 설계 문서**다.

- 시스템 범위: `EU_Back` + `EU_Front` + Neo4j KG + PostgreSQL/Render 배포 설정
- 법률 범위: EU AI Act 중심
- 상태 표기:
  - `현재 코드`: 저장소에 반영된 동작
  - `목표 반영 버전`: 최근 개선 논의(친화형 근거 전달, 하이브리드 추출 강화)를 반영한 목표 동작

---

## 1) 우리가 제공하고자 하는 가치 + 아이템

### 1-1. 문제 정의
일반적인 LLM 단독 검토에는 다음 문제가 자주 발생한다.

1. 왜 그런 판단을 했는지 근거 추적이 약함  
2. 긴 문서/복합 시나리오에서 문맥 누락이 생기기 쉬움  
3. 법률 비전문가가 결과를 읽고 실제 조치로 연결하기 어려움

이 시스템은 위 3가지를 줄이기 위해, “모델이 말한 결론”이 아니라 “근거와 연결된 진단”을 제공하는 것을 목표로 한다.

### 1-2. 제공 가치(핵심 3가지)
1. 사용자 텍스트에서 위험 신호를 찾아, **문제 가능 구간(맥락 단위)**를 이슈로 구조화  
2. 각 이슈를 EU AI Act 조항/요건과 연결해 **출처 기반 설명** 제공  
3. 법률 비전문가도 이해할 수 있게 **쉬운 설명 + 즉시 조치 문장** 제공

### 1-3. 아이템 정의
아이템명(정의): **EU AI Act 적합성 사전진단 엔진**

- 입력: 사용자 질문 + 고객 문서 텍스트(설명문, 운영정책, 창작물 설명 등)
- 처리: 이슈 추출 -> KG 검색/정합성 판정 -> 근거 제한형 생성
- 출력:
  - 리스크 레벨/점수
  - 이슈별 근거/조치
  - 관련 조항 요약(사용자 친화형)
  - 내부 검증용 트레이스(필요 시)

### 1-4. 비가치 범위(명시)
1. 법률 “확정 자문”이 아님 (사전진단 도구)
2. AI Act 외 법령 자동 자문은 기본 범위가 아님
3. 최종 법적 판단은 전문가 검토 단계 필요

---

## 2) UI/UX에서 제공하는 정보 종류와 방식

### 2-1. 사용자 화면 정보 계층
현재 UI는 “입력 -> 결과” 2단 구조이며 결과를 다시 3계층으로 보여준다.

1. 핵심 요약
- `리스크 등급`, `위험 지수`, `권고사항`

2. 설명 계층
- `핵심 설명(key_findings)`: 왜 위험인지
- `이슈 상세(issues[])`: 이슈명, 심각도, 관련 조항, 근거 문장, 조치

3. 근거 보강 계층
- `related_article_briefs`(조항 번호 + 쉬운 의미)
- `usecase_hints`, `timeline_hints`(확장 KG 사용 시)

### 2-2. 사용자 친화 원칙
`현재 코드`에서 이미 반영된 원칙:

1. 내부 상태값을 사용자 라벨로 변환  
- `grounded` -> `근거 확인`  
- `mismatch_downgraded` -> `정합성 낮음(자동 강등)`  
- `insufficient` -> `근거 부족(예비 진단)`

2. 조항 번호만 던지지 않고 설명을 붙이는 필드 제공  
- `related_article_briefs`

3. 근거 부족 시 확정형 문장을 피하고 예비진단 톤을 유지

`목표 반영 버전`에서 강화할 점:

1. “KG에서…” 같은 내부 용어 노출 최소화  
2. “사실 -> 의무 -> 위험 -> 조치” 4요소로 자동 문장화  
3. 기본 화면은 Primary 근거 위주, Supporting 경로는 펼침으로 분리

### 2-3. UI 데이터 계약(요약)
백엔드 응답에서 실제로 UI가 쓰는 핵심 필드:

- top-level: `level`, `score`, `recommendations`, `key_findings`, `issues[]`
- issue-level:
  - `theme`, `severity`
  - `evidence_status_label`
  - `related_articles`, `related_article_briefs`
  - `usecase_hints`, `timeline_hints`
  - `finding`, `recommended_action`

---

## 3) 제공 가치 달성을 위한 아키텍처 전반

## 3-1. KG 스키마를 포함한 구성 방식

### 3-1-a. E2E 데이터 흐름(상위)
```text
[사용자 입력: 질문 + 문서텍스트]
          |
          v
[LLM 이슈 신호 추출]
  (theme, trigger_terms, retrieval_keywords)
          |
          v
[Hybrid Retriever v2]
  - lexical/fulltext recall
  - control alignment
  - graph path support
  - precision-first rerank
          |
          v
[근거 정합성 게이트]
  grounded / mismatch_downgraded / insufficient
          |
          v
[근거 제한형 문장 생성]
  finding + action
          |
          v
[응답 변환 + 저장]
  VerifyResponse + DB 로그
          |
          v
[프론트 표시]
  요약/이슈/조항요약/조치
```

### 3-1-b. 지식베이스와 그래프 스키마
`현재 코드` 기준 주요 노드:

- `Article`
- `ComplianceReq`
- `Obligation`
- `Penalty`
- `UseCase`
- `Timeline`
- `Actor` (요건 적용 주체 힌트)

`현재 코드` 기준 주요 관계:

- `(:ComplianceReq)-[:DEFINED_IN]->(:Article)`
- `(:Obligation)-[:DEFINED_IN]->(:Article)`
- `(:Article)-[:REFERENCES]->(:Article)`
- `(:UseCase)-[:CLASSIFIED_AS]->(:Riskcategory)`
- `(:UseCase)-[:REFERENCES]->(:Article)`
- `(:Timeline)-[:IMPLEMENTS]->(:Article)`
- `(:ComplianceReq)-[:APPLIES_TO]->(:Actor)`

### 3-1-c. KG 확장(규칙형 추출)
KG는 단순 “문서 저장소”가 아니라, 추출된 엔티티를 다시 관계로 연결해 리트리버가 활용하도록 설계됐다.

- `UseCase`: Annex III 중심 고위험 사례 룰 기반 추출
- `ComplianceReq`: Article 9~15의 shall/must 패턴 추출
- `Timeline`: 시행시점/날짜 표현 추출

즉, “조항 텍스트 검색”과 “의무/사용사례/시행시점 연결”을 동시에 제공한다.

## 3-2. 검색 과정을 포함한 상호작용

### 3-2-a. 검색 입력 정규화
이슈 단위로 다음을 만든다.

1. `theme`
2. `trigger_terms`
3. `retrieval_keywords`
4. 확장 키워드/동의어
5. 기대 통제코드(`expected_control_codes`)

핵심은 LLM이 이슈를 제안해도 **조항 후보는 리트리버가 다시 찾는다**는 점이다.

### 3-2-b. Retriever v2 구조(정밀도 우선)
`현재 코드`의 v2는 3축 점수 결합 방식이다.

1. Lexical score (fulltext + fallback)
2. Token overlap score (BM25-like)
3. Control alignment score (기대 통제코드 일치)
4. Path support score (그래프 경로 보강)

요구사항 evidence는 아래 방식으로 엄격하게 거른다.

- `final_score >= threshold` 통과
- control 불일치 + 약한 path/token은 drop
- 동일 article 과다 선택 cap
- 엄격 필터 후 비어 있으면 soft fallback(제한적으로)

이 구조가 “아무거나 많이 찾는” 리콜보다 “관련성 높은 근거 우선”을 목표로 한다.

### 3-2-c. 검색/생성 상호작용 흐름(세부)
```text
Issue(theme) 생성
   |
   +--> expected_control_codes 계산
   |
   +--> Requirement/Obligation/Article 후보 수집
   |
   +--> score 결합 + cut-off
   |
   +--> selected evidence + trace 확정
   |
   +--> alignment 평가
            |- grounded
            |- mismatch_downgraded
            |- insufficient
   |
   +--> finding/action 생성 (채택 근거만 사용)
```

## 3-3. 생성 과정을 포함한 상호작용

### 3-3-a. 생성 제한 정책
생성 품질의 핵심은 “유창성”보다 “근거 정합성”이다.

1. 채택된 근거로만 설명 생성
2. 불일치 시 자동 강등(`mismatch_downgraded`)
3. 근거 부족 시 예비진단(`insufficient`) 톤 강제

### 3-3-b. 사용자형 문장 변환
`현재 코드`는 이미 한국어 친화형 문장을 만들고, 액션까지 자동 생성한다.

- finding: 문제 맥락 + 조항/요건 확인 사실
- action: 우선 통제 + 실행 힌트

`목표 반영 버전`에서는 다음을 강화해야 한다.

1. 조항 번호 대신 조항 의미를 기본 우선 노출
2. Primary 근거와 Supporting 경로 분리 노출
3. 내부 트레이스는 전문가용 펼침으로 제한

### 3-3-c. 결과 조립
최종 응답은 다음을 결합한다.

1. `summary`(risk_level, risk_score, counts)
2. `key_findings`
3. `issues[]`(이슈 상세 + 근거 상태 + 조치)
4. `meta`(retriever version/profile/shadow/debug)

---

## 4) 모든 부분을 설명하기 위한 코드 스니펫
아래 스니펫은 저장소 실제 파일에서 발췌한 “설명용 최소 코드”다.

### 4-1. API 진입 및 파이프라인 호출
파일: `EU_Back/app/api/endpoints/ai.py`
```python
@router.post("/verify", response_model=VerifyResponse)
def verify_system(request: VerifyRequest, db: Session = Depends(get_db)) -> VerifyResponse:
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    retriever_mode = str(os.getenv("WEB_LAB_RETRIEVER_MODE", "v2")).strip().lower() or "v2"
    retriever_shadow = _is_truthy(os.getenv("WEB_LAB_RETRIEVER_SHADOW", "false"), default=False)
    retriever_profile = str(os.getenv("WEB_LAB_RETRIEVER_PROFILE", "precision_first")).strip().lower() or "precision_first"
    friendly_text = _is_truthy(os.getenv("WEB_LAB_FRIENDLY_TEXT", "true"), default=True)
    article_diversity = _is_truthy(os.getenv("WEB_LAB_ARTICLE_DIVERSITY", "true"), default=True)
    extended_kg = _is_truthy(os.getenv("WEB_LAB_EXTENDED_KG", "true"), default=True)

    customer_text = str(request.description or "").strip()
    user_question = str(request.system_name or "").strip()

    graph = None
    try:
        graph = Neo4jQueryAdapter(uri=neo4j_uri, username=neo4j_username, password=neo4j_password)
        report = run_intent_rag_assessment(
            graph=graph,
            customer_text=customer_text,
            user_question=user_question,
            model_name=model_name,
            top_k_usecases=3,
            retriever_mode=retriever_mode,
            retriever_shadow=retriever_shadow,
            retriever_profile=retriever_profile,
            friendly_text=friendly_text,
            article_diversity=article_diversity,
            extended_kg=extended_kg,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Verify pipeline failed: {exc}")
```

### 4-2. 공개 응답 타입(프론트 계약)
파일: `EU_Back/app/schemas/verify.py`
```python
class VerifyIssue(BaseModel):
    issue_id: str
    theme: str
    severity: str
    evidence_status: Optional[str] = None
    evidence_status_label: Optional[str] = None
    related_articles: List[str] = Field(default_factory=list)
    related_article_briefs: List[str] = Field(default_factory=list)
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
```

### 4-3. LLM 이슈 추출(검색용 신호 생성)
파일: `EU_Back/src/intent_rag_diagnoser.py`
```python
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
```

### 4-4. 리트리버 v2 핵심(점수 결합 + 정밀도 필터)
파일: `EU_Back/src/intent_retriever_v2.py`
```python
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
```

```python
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

    req_candidates.sort(key=lambda x: (-float(x.get("_final_score", 0.0)), str(x.get("article_id", "")), str(x.get("req_id", ""))))
    selected_requirements: List[Dict[str, Any]] = []
    article_cap: Dict[str, int] = {}
    for item in req_candidates:
        article_id = str(item.get("article_id", ""))
        if article_cap.get(article_id, 0) >= 2:
            continue
        article_cap[article_id] = article_cap.get(article_id, 0) + 1
        selected_requirements.append({...})

    # strict가 너무 강해 비는 경우, control-aligned 후보만 제한적으로 복구
    if not selected_requirements and aligned_pool:
        ...
```

### 4-5. 근거 정합성 게이트 + 문장 생성
파일: `EU_Back/src/intent_rag_diagnoser.py`
```python
alignment = _evaluate_evidence_alignment(
    theme=str(item.get("theme", "")),
    retrieval_keywords=list(item.get("retrieval_keywords", [])),
    trigger_terms=list(item.get("trigger_terms", [])),
    requirement_evidence=requirement_evidence,
    obligation_evidence=obligation_evidence,
)
evidence_status = str(alignment.get("status", "insufficient")).strip() or "insufficient"
original_severity = str(item.get("severity", "medium")).strip().lower()
effective_severity = original_severity
effective_risk_points = int(item.get("risk_points", 0) or 0)
if evidence_status == "insufficient":
    effective_risk_points = 0
elif evidence_status == "mismatch_downgraded":
    effective_severity = _downgrade_severity(original_severity)
    ...

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
recommended_action = _build_grounded_action(...)
```

```python
def _build_grounded_action(...):
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
```

### 4-6. KG 스키마 확장 추출/적재
파일: `EU_Back/src/schema_extractor.py`
```python
def extract_use_cases(chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract 8 Annex III use-cases with deterministic keyword rules."""
    use_cases: List[Dict[str, Any]] = []
    full_text = " ".join(_normalize_space(str(c.get("content", ""))) for c in chunks).lower()
    ...
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
```

```python
def load_schema_entities_to_neo4j(schema_data: Dict[str, List[Dict[str, Any]]], graph: Any) -> Dict[str, int]:
    for item in schema_data.get("use_cases", []):
        cypher = """
        MERGE (u:UseCase {id: $id})
        SET u.title = $title, u.annex_point = $annex_point, u.keyword_hit_count = $keyword_hit_count
        WITH u
        MERGE (r:Riskcategory {id: 'High-Risk'})
        MERGE (u)-[:CLASSIFIED_AS]->(r)
        """
        ...
        MERGE (u)-[:REFERENCES]->(a)

    for item in schema_data.get("compliance_reqs", []):
        MERGE (c:ComplianceReq {id: $id})
        MERGE (c)-[:DEFINED_IN]->(a)
        ...

    for item in schema_data.get("timelines", []):
        MERGE (t:Timeline {id: $id})
        MERGE (t)-[:IMPLEMENTS]->(a)
```

### 4-7. 프론트 표시(요약/이슈/조항 요약)
파일: `EU_Front/src/pages/Verify.jsx`
```jsx
const response = await api.post('/ai/verify', {
  system_name: userQuestion,
  description,
});
setResult(response.data);
...
{(result.recommendations || []).map((rec, idx) => (
  <li key={idx}> ... {rec}</li>
))}

{Array.isArray(result.key_findings) && result.key_findings.length > 0 && (
  <ul>{result.key_findings.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
)}

{Array.isArray(result.issues) && result.issues.length > 0 && (
  <div>
    {result.issues.map((issue, idx) => (
      <div key={issue.issue_id || `issue-${idx}`}>
        <span>{(issue.severity || 'unknown').toUpperCase()}</span>
        {issue.evidence_status && (
          <span>{issue.evidence_status_label || issue.evidence_status}</span>
        )}
        <p>{issue.theme}</p>
        ...
      </div>
    ))}
  </div>
)}
```

### 4-8. 배포 환경 변수(리트리버/외부연결)
파일: `render.yaml`
```yaml
services:
  - type: web
    name: eu-backend
    env: python
    envVars:
      - key: WEB_LAB_RETRIEVER_MODE
        value: v2
      - key: WEB_LAB_RETRIEVER_SHADOW
        value: "false"
      - key: WEB_LAB_RETRIEVER_PROFILE
        value: precision_first
      - key: NEO4J_URI
        sync: false
      - key: NEO4J_USERNAME
        sync: false
      - key: NEO4J_PASSWORD
        sync: false
      - key: OPENAI_API_KEY
        sync: false
```

---

## 5) 현재 시스템이 가치 요구사항을 얼마나 충족하는가

### 5-1. 강점(충족되는 부분)
1. 단순 키워드 출력이 아니라, 이슈별 근거 상태를 분리해 출력한다.  
2. 근거 부족/불일치를 자동 강등하는 안전장치가 있다.  
3. 사용자 화면에 조항 요약과 즉시 조치가 함께 표시된다.  
4. v2 리트리버는 control alignment와 path support를 같이 사용한다.  
5. UseCase/Timeline 힌트를 통해 조항 번호 나열을 보완한다.

### 5-2. 한계(남아 있는 부분)
1. UI 기본 화면에서 내부 근거(요건/경로)가 여전히 축약되어 보일 수 있다.  
2. LLM 이슈 추출 단계는 AI Act 텍스트를 직접 읽는 단계가 아니라 “신호 추출” 단계다.  
3. 특정 범용 조항(예: 투명성/추적성)으로 몰리는 현상이 데이터/스코어 구조상 일부 남을 수 있다.

### 5-3. 결론(중간점검 관점)
이 시스템은 “LLM 단독 답변기”가 아니라, **근거 제약형 진단 파이프라인**으로서 핵심 방향은 합리적이다.  
다만 비전문가 대상 가치(쉽게 이해 + 직접 판단 가능)를 완성하려면 다음이 중요하다.

1. 기본 화면에서 Primary 근거 가독성 강화  
2. Supporting 경로는 상세로 분리해 과밀도 감소  
3. 이슈 추출의 하이브리드화(LLM + 규칙/사전 + KG 신호)를 더 명시적으로 운영

---

## 6) 검토자가 이 문서만으로 확인할 수 있는 체크리스트

1. 목적 적합성  
- “무엇을 해결하려는가”가 문제정의/가치/비범위로 분리돼 있는가

2. 재현 가능성  
- API 진입점, 주요 함수, 응답 스키마, 배포 변수까지 추적 가능한가

3. 근거 정합성 설계  
- 리트리버 점수, 강등 로직, 생성 제한 정책이 명시돼 있는가

4. 사용자 친화성 설계  
- 내부 용어를 사용자 라벨로 변환하는 규칙이 존재하는가

5. 확장성  
- KG 스키마(UseCase/Requirement/Timeline)가 검색/설명 품질 향상에 연결되는가

---

## 부록 A. 내부 용어 간단 사전

- `grounded`: 근거가 충분해 확정형 설명 가능  
- `mismatch_downgraded`: 근거는 일부 있으나 설명-근거 일치도가 낮아 자동 강등  
- `insufficient`: 근거 부족, 예비진단 톤만 허용  
- `Primary evidence`: 직접 의무/요건 근거  
- `Supporting evidence`: 참조 경로/보강 근거

---

## 부록 B. 문서 범위와 신뢰성 선언
이 문서는 코드/설정 기반의 시스템 설명서이며, 법률 자문 문서가 아니다.  
결과 해석의 최종 책임은 운영 주체와 법률 전문가 검토 단계에 있다.

