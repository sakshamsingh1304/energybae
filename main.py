import os
import tempfile
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from extraction import extract_with_groq
from validation import validate_and_clean
from excel_handler import inject_into_excel

load_dotenv()

app = FastAPI(title="EnergyBae Solar Calculator API")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConsumerData(BaseModel):
    consumer_name: str | None = None
    consumer_number: str | None = None
    connection_type: str | None = None
    sanctioned_load: str | None = None
    fixed_charges: float | None = None
    bill_amount: float | None = None
    monthly_consumption: List[Dict[str, Any]] = []

class GenerateRequest(BaseModel):
    consumers: List[ConsumerData]

@app.post("/api/extract")
async def extract_bill(file: UploadFile = File(...)):
    """Extracts data from a single bill image."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured in .env")
        
    contents = await file.read()
    try:
        raw_data = extract_with_groq(contents, file.filename, api_key)
        cleaned_data = validate_and_clean(raw_data)
        return cleaned_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



from fastapi import Form
import json

@app.post("/api/generate")
async def generate_proposal(payload: str = Form(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """Injects consumer data into the Excel template and returns the file natively."""
    try:
        # Parse the JSON string from the form data
        data = json.loads(payload)
        request = GenerateRequest(**data)
        
        # Convert Pydantic models to dicts for excel_handler
        consumers_list = [c.model_dump() for c in request.consumers]
        
        result_io = inject_into_excel(consumers_list)
        
        # Return the excel file strictly as a downloadable attachment directly from memory
        content = result_io.getvalue()
        headers = {
            "Content-Disposition": 'attachment; filename="Energybae_Customer_Proposal.xlsx"',
            "Content-Length": str(len(content)),
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
        from fastapi import Response
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files (Frontend UI)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
