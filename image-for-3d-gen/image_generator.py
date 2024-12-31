import torch
from PIL import Image
import base64
import io
from diffusers import FluxPipeline
from transformers import pipeline
from huggingface_hub import hf_hub_download
import os


class ImageGeneratorDummy:
    def __init__(self):
        pass
    
    def generate(self, prompt, height=1024, width=1024, steps=8, scales=3.5, seed=None):
        print(f"generate dummy image for {prompt}")
        # generate dummy image
        image = Image.new("RGB", (height, width), (255, 255, 255))
        image_base64 = self.image_to_base64(image)
        return {
            "image_base64": image_base64,
            "seed": 123456
        }
    
    @staticmethod
    def image_to_base64(image):
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    
class ImageGenerator:
    def __init__(self):
        # Initialize translator
       
        # Initialize Flux pipeline
        self.pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev",
            torch_dtype=torch.bfloat16,
            use_auth_token=os.getenv("HF_TOKEN")
        )
        
        # Load and fuse LoRA weights
        self.pipe.load_lora_weights(
            hf_hub_download(
                "ByteDance/Hyper-SD",
                "Hyper-FLUX.1-dev-8steps-lora.safetensors",
                use_auth_token=os.getenv("HF_TOKEN")
            )
        )
        self.pipe.fuse_lora(lora_scale=0.125)
        self.pipe.to(device="cuda", dtype=torch.bfloat16)

    @staticmethod
    def contains_korean(text):
        return any(ord('가') <= ord(c) <= ord('힣') for c in text)

    @staticmethod
    def image_to_base64(image):
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    def generate(self, prompt, height=1024, width=1024, steps=8, scales=3.5, seed=None):
        
        # Format prompt
        formatted_prompt = f"wbgmsst, 3D, {prompt} ,white background"
        
        # Set seed if not provided
        if seed is None:
            seed = torch.randint(0, 1000000, (1,)).item()
        
        # Generate image
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            generated_image = self.pipe(
                prompt=[formatted_prompt],
                generator=torch.Generator().manual_seed(seed),
                num_inference_steps=steps,
                guidance_scale=scales,
                height=height,
                width=width,
                max_sequence_length=256
            ).images[0]
        
        # Convert to base64
        image_base64 = self.image_to_base64(generated_image)
        
        return {
            "image_base64": image_base64,
            "seed": seed
        } 