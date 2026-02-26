from fastapi import APIRouter

router = APIRouter()

@router.post("/chat")
def chat_with_ai(prompt: str):
    # TODO: Integrate real RAG logic here
    return {"message": "Dummy AI Response for: " + prompt}
