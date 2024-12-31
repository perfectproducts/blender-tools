import io
import base64
from PIL import Image

class DummyImageGenerator:
    def __init__(self):
        pass
    
    def generate(self, prompt, height=1024, width=1024, steps=8, scales=3.5, seed=None):
        print(f"generate dummy image for {prompt}")
        # read dummy_result.png and scale it to the desired size
        image = Image.open("dummy_result.png")
        image = image.resize((height, width))

        image_base64 = self.image_to_base64(image)
        return {
            "image_base64": image_base64,
            "seed": 123456 if seed is None else seed
        }
    
    @staticmethod
    def image_to_base64(image):
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()