from pydantic import BaseModel
from typing import List, Optional

class VerifyRequest(BaseModel):
    system_name: str
    description: str

class VerifyResponse(BaseModel):
    level: str
    score: int
    recommendations: List[str]
