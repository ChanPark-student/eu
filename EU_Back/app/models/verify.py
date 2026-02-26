from sqlalchemy import Column, Integer, String, JSON
from app.db.database import Base

class VerifyReport(Base):
    __tablename__ = "verify_reports"

    id = Column(Integer, primary_key=True, index=True)
    system_name = Column(String, index=True)
    description = Column(String)
    level = Column(String)
    score = Column(Integer)
    recommendations = Column(JSON)
