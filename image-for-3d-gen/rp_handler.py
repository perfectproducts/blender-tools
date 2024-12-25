import runpod
from image_generator import ImageGenerator

# Initialize generator
generator = ImageGenerator()

def handler(event):
    try:
        input_data = event["input"]
        return generator.generate(
            prompt=input_data.get("prompt"),
            height=input_data.get("height", 1024),
            width=input_data.get("width", 1024),
            steps=input_data.get("steps", 8),
            scales=input_data.get("scales", 3.5),
            seed=input_data.get("seed")
        )
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler}) 