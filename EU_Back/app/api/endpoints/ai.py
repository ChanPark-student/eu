from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.verify import VerifyReport
from app.schemas.verify import VerifyRequest, VerifyResponse
import time

router = APIRouter()

@router.post("/chat")
def chat_with_ai(prompt: str):
    # TODO: Integrate real RAG logic here
    return {"message": "Dummy AI Response for: " + prompt}

@router.post("/verify", response_model=VerifyResponse)
def verify_system(request: VerifyRequest, db: Session = Depends(get_db)):
    # Simulate processing delay
    time.sleep(3)
    
    # Simulate AI analysis result
    simulated_result = {
        "level": "High Risk",
        "score": 82,
        "recommendations": [
            "인간의 감독(Human Oversight) 메커니즘을 명시적으로 문서화하십시오.",
            "데이터 편향성(Data Bias) 검증 리포트를 추가로 제출해야 합니다.",
            "사용자에게 AI와 상호작용하고 있음을 명확히 고지하십시오."
        ]
    }
    
    # Save to PostgreSQL
    db_report = VerifyReport(
        system_name=request.system_name,
        description=request.description,
        level=simulated_result["level"],
        score=simulated_result["score"],
        recommendations=simulated_result["recommendations"]
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    
    return VerifyResponse(**simulated_result)
