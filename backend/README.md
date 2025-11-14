Backend (FastAPI) — AIRR POC

Run requirements
- Python 3.11+
- LibreOffice (`soffice`) in PATH or set `LIBREOFFICE_PATH`

Install
1) Create and activate venv
2) pip install -r backend/requirements.txt

Environment
- Copy `.env.example` to `.env` at the repo root and fill values (for reference/shared defaults).
- For Docker Compose, `backend/.env.local` is loaded automatically (see docker-compose.yml `env_file`).
- For local (non-Docker) runs, set OS env vars or create `backend/.env.local` (read by Pydantic settings).

Required variables
- MONGO_URI=mongodb://localhost:27017/airr_poc
- MODEL_NAME=gpt-4o-2024-08-06 (or your chosen OpenAI model)
- MODEL_API_KEY=YOUR_OPENAI_API_KEY
- OPENAI_BASE_URL=https://api.openai.com/v1 (default; override only if using a proxy/alt provider)
- CLOUDINARY_URL=cloudinary://KEY:SECRET@CLOUD_NAME
- CLOUDINARY_BASE_FOLDER=airr-poc
- LIBREOFFICE_PATH=optional-full-path-to-soffice

Run (local)
uvicorn app.main:app --reload --port 8000 --app-dir backend

Endpoints
- POST /workbooks/upload (multipart) → { workbook_id, sheets }
- POST /workbooks/{id}/convert { sheet_name } → { pdf_url }
- POST /workbooks/{id}/extract { sheet_name? } → session + extracted payload
- GET /sessions/ → list sessions
- GET /sessions/{session_id} → session detail
- PUT /sessions/{session_id} → save final_json

Docker
- Build: docker build -f backend/Dockerfile -t airr-backend .
- Run: docker compose up --build
- Backend URL: http://localhost:8000
- Ensure `MONGO_URI` in `backend/.env.local` points to your MongoDB (e.g., Atlas connection string)

Notes
- Excel→PDF uses openpyxl + headless LibreOffice; `.xlsx`, `.xlsm`, and legacy `.xls` are supported (legacy `.xls` is first converted to `.xlsx`).
- Converter preserves layout by:
  - opening the original workbook (preserving VBA for `.xlsm`),
  - hiding non-target sheets and setting the target active,
  - applying print settings (fit to 1 page width, landscape, fitToPage, horizontal centered) and print area to used range,
  - exporting via LibreOffice Calc filter `pdf:calc_pdf_Export` (not the generic PDF filter).
- Files are stored in Cloudinary (raw), under airr-poc/workbooks/{id} and airr-poc/pdfs/{id}.
- LLM calls use OpenAI Python SDK targeting Gemini-compatible base URL.
