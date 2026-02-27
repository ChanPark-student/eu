# Render Deployment Guide (EU + Antigravity Intent RAG)

## What is included
- Backend: `EU_Back` FastAPI (`/api/ai/verify`) now calls embedded Antigravity Intent RAG.
- Frontend: `EU_Front` React app calls backend via `VITE_API_URL`.
- Blueprint: `render.yaml` (backend + frontend).

## One-time setup on Render
1. Create a new Blueprint service from this repository.
2. Render will detect `render.yaml` and create:
- `eu-backend` (Python web service)
- `eu-frontend` (Static site)
3. In `eu-backend`, set secret env vars:
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `OPENAI_API_KEY`

## Notes
- `EU_Test` is not used for deployment.
- Backend DB is SQLite (`sql_app.db`) by default. On free web instances this is ephemeral.
- If `OPENAI_API_KEY` is missing, intent extraction can degrade/fallback and result quality will drop.

## Local run quick check
### Backend
```bash
cd EU_Back
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend
```bash
cd EU_Front
npm install
# optional: set VITE_API_URL=http://127.0.0.1:8000
npm run dev
```
