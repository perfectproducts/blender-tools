from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from enum import Enum
import httpx
import os
from typing import Optional, Dict
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API keys - if none provided, API key auth is disabled
API_KEYS = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local service configuration
IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://localhost:8001")
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://localhost:8002")

# In-memory job storage
jobs: Dict[str, dict] = {}

class JobStatus(str, Enum):
    PENDING = "pending"
    GENERATING_IMAGE = "generating_image"
    GENERATING_3D = "generating_3d"
    COMPLETED = "completed"
    FAILED = "failed"

class GenerationRequest(BaseModel):
    prompt: str
    height: Optional[int] = 1024
    width: Optional[int] = 1024
    steps: Optional[int] = 8
    scales: Optional[float] = 3.5
    seed: Optional[int] = None

@app.post("/generate")
async def generate_combined(request: GenerationRequest, authorization: str = Header(None)):
    # Verify API key only if API_KEYS is configured
    if API_KEYS:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing API key")
        provided_key = authorization.replace("Bearer ", "")
        if provided_key not in API_KEYS:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": JobStatus.PENDING,
        "prompt": request.prompt,
        "image_base64": None,
        "model_base64": None,
        "error": None
    }
    
    try:
        print(f"[{job_id}] Starting generation process with prompt: {request.prompt}")
        
        async with httpx.AsyncClient(timeout=1800.0) as client:
            # Step 1: Generate image
            jobs[job_id]["status"] = JobStatus.GENERATING_IMAGE
            print(f"[{job_id}] Generating image...")
            
            image_response = await client.post(
                f"{IMAGE_SERVICE_URL}/generate",
                json={
                    "prompt": request.prompt,
                    "height": request.height,
                    "width": request.width,
                    "steps": request.steps,
                    "scales": request.scales,
                    "seed": request.seed
                }
            )

            print(f"[{job_id}] Image response: {image_response.text}")
            
            if image_response.status_code != 200:
                raise HTTPException(status_code=image_response.status_code, 
                                 detail=image_response.text)
            
            image_result = image_response.json()
            image_base64 = image_result["image_base64"]
            jobs[job_id]["image_base64"] = image_base64

            # Step 2: Generate 3D model
            jobs[job_id]["status"] = JobStatus.GENERATING_3D
            print(f"[{job_id}] Generating 3D model...")
            
            model_response = await client.post(
                f"{MODEL_SERVICE_URL}/process-image",
                json={
                    "image_base64": image_base64,
                    "mesh_simplify": 0.95,
                    "texture_size": 1024
                }
            )
            
            if model_response.status_code != 200:
                raise HTTPException(status_code=model_response.status_code, 
                                 detail=model_response.text)
            
            model_result = model_response.json()
            jobs[job_id]["model_base64"] = model_result["glb_base64"]
            jobs[job_id]["status"] = JobStatus.COMPLETED
            print(f"[{job_id}] Process completed successfully")

    except Exception as e:
        print(f"[{job_id}] Process failed with error: {str(e)}")
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "job_id": job_id,
        "status": jobs[job_id]["status"],
        "image_base64": jobs[job_id]["image_base64"],
        "model_base64": jobs[job_id]["model_base64"],
        "error": jobs[job_id]["error"]
    }

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return {
        "status": job["status"],
        "image_base64": job["image_base64"],
        "model_base64": job["model_base64"],
        "error": job["error"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 