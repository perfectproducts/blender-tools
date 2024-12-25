bl_info = {
    "name": "Text to 3D Generator",
    "author": "Your Name",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Text to 3D",
    "description": "Generate 3D models from text descriptions using RunPod",
    "category": "3D View",
}

import bpy
import requests
import json
import os
import tempfile
from bpy.props import StringProperty, BoolProperty, FloatProperty, IntProperty
import threading
import time
import base64

class TextTo3DProperties(bpy.types.PropertyGroup):
    prompt: StringProperty(
        name="Text Prompt",
        description="Describe what you want to generate",
        default=""
    )
    api_url: StringProperty(
        name="API URL",
        description="URL of the Text-to-3D API service",
        default="http://localhost:8000"
    )
    is_processing: BoolProperty(
        name="Processing",
        default=False
    )
    job_id: StringProperty(
        name="Job ID",
        default=""
    )
    mesh_simplify: FloatProperty(
        name="Mesh Simplify",
        description="Ratio of triangles to remove (0.9-0.98)",
        default=0.95,
        min=0.9,
        max=0.98
    )
    texture_size: IntProperty(
        name="Texture Size",
        description="Size of the texture used for the GLB",
        default=1024,
        min=512,
        max=2048,
        step=512
    )
    status_message: StringProperty(
        name="Status Message",
        default=""
    )
    api_key: StringProperty(
        name="API Key",
        description="Your RunPod API key",
        default="",
        subtype='PASSWORD'
    )

class OBJECT_OT_generate_3d(bpy.types.Operator):
    bl_idname = "object.generate_3d"
    bl_label = "Generate 3D Model"
    bl_description = "Generate a 3D model from text description"
    
    def execute(self, context):
        props = context.scene.text_to_3d_props
        
        if not props.prompt:
            self.report({'ERROR'}, "Please enter a text prompt")
            return {'CANCELLED'}
        
        props.is_processing = True
        threading.Thread(target=self.generate_model, args=(context,)).start()
        
        return {'FINISHED'}
    
    def generate_model(self, context):
        props = context.scene.text_to_3d_props
        base_url = props.api_url.rstrip('/')
        
        try:
            # Initial generation request
            try:
                response = requests.post(
                    f"{base_url}/generate",
                    json={
                        "prompt": props.prompt,
                        "height": 1024,
                        "width": 1024,
                        "steps": 8,
                        "scales": 3.5
                    },
                    headers={
                        "Authorization": f"Bearer {props.api_key}"
                    }
                )
            except requests.exceptions.ConnectionError:
                self.report({'ERROR'}, "Could not connect to the server. Please make sure the server is running and the API URL is correct.")
                return
            
            if response.status_code != 200:
                self.report({'ERROR'}, f"Generation failed: {response.text}")
                return
            
            result = response.json()
            job_id = result["job_id"]
            props.job_id = job_id
            
            # Poll for completion
            while True:
                status_response = requests.get(f"{base_url}/status/{job_id}")
                if status_response.status_code != 200:
                    self.report({'ERROR'}, "Failed to check status")
                    break
                
                status = status_response.json()
                
                if status["status"] == "completed":
                    # Get the base64 model data
                    model_base64 = status.get("model_base64")
                    if not model_base64:
                        self.report({'ERROR'}, "No model data received")
                        break
                    
                    # Decode base64 and save to temporary file
                    model_data = base64.b64decode(model_base64)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
                    temp_file.write(model_data)
                    temp_file.close()
                    
                    # Import the GLB file in the main thread
                    def import_handler():
                        bpy.ops.import_scene.gltf(filepath=temp_file.name)
                        os.unlink(temp_file.name)
                        props.is_processing = False
                        return None
                    
                    bpy.app.timers.register(import_handler)
                    break
                
                elif status["status"] == "failed":
                    self.report({'ERROR'}, f"Generation failed: {status.get('error', 'Unknown error')}")
                    break
                
                time.sleep(2)
                
        except Exception as e:
            self.report({'ERROR'}, f"Error: {str(e)}")
        
        finally:
            props.is_processing = False

class VIEW3D_PT_text_to_3d(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Text to 3D'
    bl_label = 'Text to 3D Generator'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.text_to_3d_props
        
        layout.prop(props, "api_url")
        layout.prop(props, "api_key")
        layout.prop(props, "prompt")
        
        # Add mesh simplification and texture size controls
        layout.prop(props, "mesh_simplify")
        layout.prop(props, "texture_size")
        
        row = layout.row()
        row.enabled = not props.is_processing
        row.operator("object.generate_3d")
        
        if props.is_processing:
            layout.label(text=props.status_message or "Processing...")

classes = (
    TextTo3DProperties,
    OBJECT_OT_generate_3d,
    VIEW3D_PT_text_to_3d,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.text_to_3d_props = bpy.props.PointerProperty(type=TextTo3DProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.text_to_3d_props

if __name__ == "__main__":
    register()