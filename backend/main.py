from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from parser import parse_routes
from models import Route
from typing import List
import shutil
import os
import time

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Tutti API"}

@app.post("/upload", response_model=List[Route])
async def upload_files(files: List[UploadFile] = File(...)):
    all_routes = []
    temp_files = []

    try:
        for file in files:
            file_location = f"temp_{file.filename}"
            temp_files.append(file_location)

            # Write file to disk
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(file.file, file_object)

            # Parse routes (file is now closed)
            routes = parse_routes(file_location)
            all_routes.extend(routes)

        if not all_routes:
            raise HTTPException(status_code=400, detail="No routes found or error parsing files")

        return all_routes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp files
        time.sleep(0.1)  # Small delay to ensure files are released
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"Warning: Could not delete temp file {temp_file}: {e}")

@app.post("/optimize", response_model=List[dict])
async def optimize(routes: List[Route]):
    try:
        from optimizer import optimize_routes
        schedule = optimize_routes(routes)
        return [s.dict() for s in schedule]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize_lp", response_model=List[dict])
async def optimize_lp(routes: List[Route]):
    try:
        from optimizer import optimize_routes_lp
        schedule = optimize_routes_lp(routes)
        return [s.dict() for s in schedule]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export_pdf")
async def export_pdf(schedule: List[dict] = Body(...)):
    try:
        from pdf_service import generate_schedule_pdf
        pdf_buffer = generate_schedule_pdf(schedule)
        
        return StreamingResponse(
            pdf_buffer, 
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=schedule.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
