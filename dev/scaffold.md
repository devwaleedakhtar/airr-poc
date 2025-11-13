## **Goal**

Users (real estate analysts) upload an Excel workbook → select a sheet → backend converts that sheet to a clean PDF → LLM extracts tables/values → frontend displays extracted data in a “Review & Fix” UI → user saves the final standardized JSON.

---

## **Core Challenges**

- Uploaded Excel files are **not standardized** (different layouts/headers/naming).
- Extraction must be flexible: tables may have headers or no headers.
- LLM extraction may be incomplete → require a reviewer UI.

---

# **Backend Requirements (FastAPI)**

## **Tech**

- Python + FastAPI
- Use **latest OpenAI SDK package**, but call **Gemini API for now**

  - `.env` will include:

    - `MONGO_URI`
    - `MODEL_NAME` (e.g., gemini-2.5-flash — don’t hardcode)
    - `MODEL_API_KEY`

- Database: **MongoDB**

  - Store each extraction “run” as a **session**
  - Expose endpoint to list all sessions
  - Expose endpoint to view a single session

---

## **Architecture**

Use clean modular structure:

```
backend/
  ├── services/
  │     ├── converter_service.py   # Excel → single-sheet PDF
  │     ├── extractor_service.py   # PDF → LLM → extracted JSON
  ├── prompts/
  │     └── extraction_prompt.txt
  ├── routes/
  │     ├── workbook.py
  │     └── sessions.py
```

---

## **Converter Logic (Excel → PDF)**

Conversion must replicate logic from the reference script:

- Load workbook (xls / xlsm / xlsx)
- **Hide all sheets except the selected one**
- Autofit columns
- Fit sheet to single-page PDF width
- Detect used range → set print area
- Generate **clean PDF of the selected sheet only**
- Temporary file cleanup
- Return path to generated PDF

(Logic should be cleanly reusable by other endpoints.)

---

## **Extraction Logic (PDF → LLM → JSON)**

- Prompt stored under `prompts/extraction_prompt.txt`
- Extract tables into JSON structure:

```json
{
  "Table Name": {
    "key": "value",
    ...
  }
}
```

- If no header found, infer a “logical” table name based on field names.
- API returns:

  - extracted JSON
  - confidence per field (optional but helpful)
  - list of inferred vs exact tables
  - any warnings

---

## **Backend Endpoints**

### **POST /workbooks/upload**

- Accept Excel file
- Return: `{ workbook_id, sheets: [...] }`

### **POST /workbooks/{id}/convert**

- Input: `{ sheet_name }`
- Output: `{ pdf_url }`

### **POST /workbooks/{id}/extract**

- Runs LLM extraction on generated PDF
- Saves extracted run as a **session**
- Return structured data for frontend “Review & Fix”

### **GET /sessions**

- Return list of previous runs

### **GET /sessions/{session_id}**

- Return stored session

---

# **Frontend Requirements (Next.js + ShadCN)**

### **UI Stack**

- Next.js App Router
- TypeScript
- ShadCN components
- Clean, professional, analyst-friendly UX

---

## **Frontend Flow**

### **1. Upload Page**

- File dropzone for Excel
- Backend returns list of sheets
- Dropdown to select sheet (default to “Input” if exists)
- “Extract” button

### **2. Under-the-hood Processing**

- Call backend convert → extract
- Show progress indicators:

  - “Analyzing workbook…”
  - “Extracting assumptions…”

### **3. Review & Fix Page**

Display extracted data grouped by sections (LLM output):

Each field row:

- Label
- Editable input
- Confidence badge:

  - High (green)
  - Medium (yellow – needs review)
  - Low/Not found (red, required)

Missing/incomplete fields must be manually filled.

Optional:

- Side panel showing matched source text snippets

Action:

- “Save & Continue” → final JSON saved to session

### **4. Sessions Page**

- List all previous sessions
- Click to view previous extraction results (read-only)

---

# **Additional Notes**

- Ensure backend services are reusable and modular.
- Keep the codebase clean and organized for future expansion (chatbot, ingestion pipeline).
