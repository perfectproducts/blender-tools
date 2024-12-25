from fastapi import FastAPI, HTTPException, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from enum import Enum
import httpx
import os
import asyncio
from typing import Optional, Dict
import uuid
from dotenv import load_dotenv

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Updated RunPod configuration
RUNPOD_IMAGE_ENDPOINT_ID = os.getenv("RUNPOD_IMAGE_ENDPOINT_ID")
RUNPOD_3D_ENDPOINT_ID = os.getenv("RUNPOD_3D_ENDPOINT_ID")
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY", "")

# In-memory job storage
jobs: Dict[str, dict] = {}

# Add near the top with other configuration
USE_API_KEY = os.getenv("USE_API_KEY")  # The API key that clients must provide to access this service

# Load environment variables
load_dotenv()

# Get API keys - if none provided, API key auth is disabled
API_KEYS = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []

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
        "image_path": None,
        "model_path": None,
        "error": None
    }
    
    # Start the generation process in the background
    asyncio.create_task(process_generation(job_id, request))
    
    return {"job_id": job_id, "status": JobStatus.PENDING}

async def process_generation(job_id: str, request: GenerationRequest):
    try:
        print(f"[{job_id}] Starting generation process with prompt: {request.prompt}")
        jobs[job_id]["status"] = JobStatus.GENERATING_IMAGE
        print(f"[{job_id}] Status updated to: {JobStatus.GENERATING_IMAGE}")
        
        async with httpx.AsyncClient(timeout=2800.0) as client:
            print(f"[{job_id}] Sending image generation request to RunPod endpoint: {RUNPOD_IMAGE_ENDPOINT_ID}")
            
            # Step 1: Generate image
            print(f"[{job_id}] Sending image generation request to https://api.runpod.ai/v2/{RUNPOD_IMAGE_ENDPOINT_ID}/run")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {RUNPOD_API_KEY}"
            }
            
            # Step 1: Generate image (mostly unchanged)
            image_response = await client.post(
                f"https://api.runpod.ai/v2/{RUNPOD_IMAGE_ENDPOINT_ID}/run",
                json={
                    "input": {
                        "prompt": request.prompt,
                        "height": request.height,
                        "width": request.width,
                        "steps": request.steps,
                        "scales": request.scales,
                        "seed": request.seed
                    }
                },
                headers=headers
            )
            
            if image_response.status_code != 200:
                raise HTTPException(status_code=image_response.status_code, detail=image_response.text)
            
            image_job = image_response.json()
            image_job_id = image_job["id"]
            
            print(f"[{job_id}] Image generation job created with ID: {image_job_id}")
            
            # Poll for image completion
            while True:
                print(f"[{job_id}] Polling image generation status...")
                status_response = await client.get(
                    f"https://api.runpod.ai/v2/{RUNPOD_IMAGE_ENDPOINT_ID}/status/{image_job_id}",
                    headers=headers
                )
                
                status_data = status_response.json()
                print(f"[{job_id}] Image status: {status_data['status']}")
                
                if status_data["status"] == "COMPLETED":
                    print(f"[{job_id}] Image generation completed successfully")
                    image_result = status_data["output"]
                    break
                elif status_data["status"] == "FAILED":
                    print(f"[{job_id}] Image generation failed with error: {status_data.get('error', 'Unknown error')}")
                    raise Exception(f"Image generation failed: {status_data.get('error', 'Unknown error')}")
                
                await asyncio.sleep(2)

            image_base64 = image_result["image_base64"]
            jobs[job_id]["image_base64"] = image_base64

            # Step 2: Generate 3D model using RunPod
            jobs[job_id]["status"] = JobStatus.GENERATING_3D
            print(f"[{job_id}] Starting 3D generation with RunPod endpoint: {RUNPOD_3D_ENDPOINT_ID}")
            
            model_response = await client.post(
                f"https://api.runpod.ai/v2/{RUNPOD_3D_ENDPOINT_ID}/run",
                json={
                    "input": {
                        "image_base64": image_base64,
                        "mesh_simplify": 0.95,
                        "texture_size": 1024
                    }
                },
                headers=headers
            )
            
            if model_response.status_code != 200:
                raise HTTPException(status_code=model_response.status_code, detail=model_response.text)
            
            model_job = model_response.json()
            model_job_id = model_job["id"]
            
            print(f"[{job_id}] 3D generation job created with ID: {model_job_id}")
            
            # Poll for 3D model completion
            while True:
                print(f"[{job_id}] Polling 3D generation status...")
                status_response = await client.get(
                    f"https://api.runpod.ai/v2/{RUNPOD_3D_ENDPOINT_ID}/status/{model_job_id}",
                    headers=headers
                )
                
                status_data = status_response.json()
                print(f"[{job_id}] 3D model status: {status_data['status']}")
                
                if status_data["status"] == "COMPLETED":
                    print(f"[{job_id}] 3D generation completed successfully")
                    model_result = status_data["output"]
                    break
                elif status_data["status"] == "FAILED":
                    print(f"[{job_id}] 3D generation failed with error: {status_data.get('error', 'Unknown error')}")
                    raise Exception(f"3D generation failed: {status_data.get('error', 'Unknown error')}")
                
                await asyncio.sleep(2)

            jobs[job_id]["model_base64"] = model_result["glb_base64"]
            jobs[job_id]["status"] = JobStatus.COMPLETED
            print(f"[{job_id}] Process completed successfully")

    except Exception as e:
        print(f"[{job_id}] Process failed with error: {str(e)}")
        print(e)
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["error"] = str(e)

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return {
        "status": job["status"],
        "image_base64": job["image_base64"] if job["status"] in [JobStatus.GENERATING_3D, JobStatus.COMPLETED] else None,
        "model_base64": job["model_base64"] if job["status"] == JobStatus.COMPLETED else None,
        "error": job["error"] if job["status"] == JobStatus.FAILED else None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 