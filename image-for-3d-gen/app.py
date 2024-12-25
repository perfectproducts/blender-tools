import os
import time
from os import path
from datetime import datetime
from safetensors.torch import load_file
from huggingface_hub import hf_hub_download
import torch
from diffusers import FluxPipeline
from PIL import Image
from transformers import pipeline
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from image_generator import ImageGenerator

app = FastAPI()

# Initialize generator
generator = ImageGenerator()

# Remove old initialization code and keep only the relevant parts
torch.backends.cuda.matmul.allow_tf32 = True

class GenerationRequest(BaseModel):
    prompt: str
    height: Optional[int] = 1024
    width: Optional[int] = 1024
    steps: Optional[int] = 8
    scales: Optional[float] = 3.5
    seed: Optional[int] = None

@app.post("/generate")
async def generate_image(request: GenerationRequest):
    try:
        result = generator.generate(
            prompt=request.prompt,
            height=request.height,
            width=request.width,
            steps=request.steps,
            scales=request.scales,
            seed=request.seed
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)