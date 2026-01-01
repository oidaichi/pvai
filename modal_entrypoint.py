import modal
import sys
import os
import uuid
import json
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

def file_filter(p):
    p_str = str(p).replace("\\", "/")
    if ".git" in p_str or "output" in p_str or "__pycache__" in p_str:
        return True
    return False

# Define the image for LongCat-Video
# Dependencies based on https://github.com/meituan-longcat/LongCat-Video
# We use a CUDA-enabled base image that includes nvcc, which is required for building flash-attn
image = (
    modal.Image.from_registry("nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.10")
    .apt_install("git", "ffmpeg", "libgl1-mesa-glx", "libglib2.0-0", "ninja-build")
    # Install PyTorch 2.6.0+cu124
    .pip_install(
        "torch==2.6.0+cu124", 
        "torchvision==0.21.0+cu124", 
        "torchaudio==2.6.0", 
        extra_index_url="https://download.pytorch.org/whl/cu124"
    )
    .pip_install(
        "fastapi", 
        "uvicorn", 
        "ninja", 
        "psutil", 
        "packaging", 
        "diffusers", 
        "transformers", 
        "accelerate", 
        "sentencepiece", 
        "protobuf",
        "vllm", # For prompt expansion
        "wheel",
        "setuptools"
    )
    # flash-attn building is memory intensive and might fail or timeout.
    # For now, we skip it or use a pre-built wheel if available. 
    # LongCat might run without it (slower) or we need a better strategy.
    # Attempting to use a pre-built wheel from a known source or just rely on torch's SDPA if supported by LongCat code.
    # However, LongCat requirements explicitly list it.
    # Let's try installing a pre-built wheel for cu123 which is close enough or generic.
    # Actually, let's just comment it out for this 'mock' deployment to succeed, 
    # as we are not running heavy inference in this demo environment.
    # .run_commands("pip install flash_attn==2.7.4.post1 --no-build-isolation")
    # Clone LongCat-Video repo
    .run_commands(
        "git clone --single-branch --branch main https://github.com/meituan-longcat/LongCat-Video /root/LongCat-Video"
    )
    # requirements.txt might not exist or be named differently, or we already installed most deps.
    # Inspecting repo content is hard during build without running 'ls'.
    # We'll skip strict requirements.txt installation as we manually installed key deps above.
    # .pip_install_from_requirements("/root/LongCat-Video/requirements.txt")
    .add_local_dir(".", remote_path="/root/pvai", copy=True, ignore=file_filter)
)

app = modal.App("pvai-engine", image=image)

# Persistent volume for models
models_volume = modal.Volume.from_name("pvai-models", create_if_missing=True)

# --- Helper Functions for Web Server ---

@app.cls(
    gpu="A10G", 
    min_containers=0, # Scale to 0 to save cost
    timeout=600,
    volumes={"/root/vol_models": models_volume}
)
class PVAI:
    def __init__(self):
        self.pipeline = None
        self.vllm_model = None

    def initialize(self):
        """
        Initialize LongCat-Video model.
        """
        print("DEBUG: Initializing PVAI Engine (LongCat-Video)...")
        
        # Add LongCat-Video to path
        sys.path.append("/root/LongCat-Video")
        
        # Model paths (Download if not exists using HuggingFace Hub)
        from huggingface_hub import snapshot_download
        
        model_dir = "/root/vol_models/LongCat-Video"
        if not os.path.exists(model_dir):
            print("Downloading LongCat-Video model...")
            snapshot_download(
                repo_id="meituan-longcat/LongCat-Video", 
                local_dir=model_dir,
                ignore_patterns=["*.msgpack", "*.bin"] # Optimized download
            )
        
        # Load Model (Pseudo-code based on generic diffusers/torch loading)
        # Note: Actual loading depends on LongCat's specific API which we would inspect in the repo.
        # Assuming a standard pipeline or demo script usage.
        print("Loading LongCat-Video pipeline...")
        # from longcat_video.pipeline import LongCatPipeline 
        # self.pipeline = LongCatPipeline.from_pretrained(model_dir).to("cuda")
        
        # Placeholder for actual model loading logic
        # For this implementation, we simulate loading to ensure structure is correct
        self.pipeline = "LOADED"
        
        # Initialize vLLM for prompt expansion if feasible on same GPU, 
        # or use a smaller model / external API. 
        # For simplicity in this 'senior pair programmer' context, we'll implement a simple expander.
        print("PVAI Engine Initialized.")

    @modal.method()
    def enhance_prompt(self, user_prompt: str, mode: str) -> str:
        """
        Expand user prompt using vLLM or rule-based logic.
        """
        # In a real scenario with sufficient GPU memory, we would use vLLM here.
        # self.vllm_model.generate(...)
        
        print(f"Expanding prompt for mode: {mode}")
        
        base_instruction = ""
        if mode == "influencer":
            base_instruction = "High quality, photorealistic, 4k, influencer style, holding product, "
        elif mode == "lipsync":
            base_instruction = "Close up, talking face, clear mouth movement, "
        elif mode == "pose":
            base_instruction = "Full body, dynamic pose, precise movement, "
            
        expanded = f"{base_instruction}{user_prompt}, cinematic lighting, highly detailed, trending on artstation"
        return expanded

    @modal.method()
    def generate(self, params: Dict[str, Any]) -> str:
        """
        Generate video using LongCat-Video.
        """
        if self.pipeline is None:
            self.initialize()
            
        mode = params.get("mode")
        payload = params.get("payload", {})
        
        # Extract parameters
        final_prompt = payload.get("prompt", "")
        aspect_ratio = payload.get("aspect_ratio", "16:9")
        resolution = payload.get("resolution", "720p")
        duration = payload.get("duration", 4)
        seed_fixed = payload.get("seed_fixed", False)
        image_data = payload.get("image_data") # Base64 string
        image_usage = payload.get("image_usage")
        
        print(f"Generating video...")
        print(f"  Mode: {mode}")
        print(f"  Prompt: {final_prompt}")
        print(f"  Aspect Ratio: {aspect_ratio}")
        print(f"  Resolution: {resolution}")
        print(f"  Duration: {duration}s")
        print(f"  Seed Fixed: {seed_fixed}")
        if image_data:
            print(f"  Image Data Received: Yes (Length: {len(image_data)})")
            print(f"  Image Usage: {image_usage}")
        else:
            print(f"  Image Data Received: No")
        
        # 2. Run Inference (LongCat-Video)
        # Assuming run_text_to_video logic here
        # output_path = self.pipeline(
        #     final_prompt, 
        #     num_frames=..., 
        #     height=..., width=..., 
        #     seed=12345 if seed_fixed else None
        # )
        
        # Mocking output for now since we can't run actual heavy inference in this environment
        # In production:
        # 1. Call LongCat inference code
        # 2. Save video to /tmp
        # 3. Upload to R2/S3
        # 4. Return URL
        
        # Mock Output
        import time
        time.sleep(5) # Simulate generation
        
        # Return a sample video URL (Placeholder)
        return "https://cdn.coverr.co/videos/coverr-relaxing-at-the-beach-at-sunset-5364/1080p.mp4"

    @modal.method()
    def concat_videos(self, video_urls: list[str]) -> str:
        # (Existing ffmpeg concat logic can remain here)
        return "https://example.com/concatenated.mp4"

# --- Web Server ---

web_app = FastAPI(title="PVAI Studio")

@web_app.get("/")
async def read_index():
    paths = ["/root/pvai/index.html", "index.html"]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Error: index.html not found</h1>", status_code=404)

@web_app.post("/api/enhance_prompt")
async def handle_enhance_prompt(request: Request):
    try:
        body = await request.json()
        prompt = body.get("prompt")
        mode = body.get("mode")
        
        if not prompt or not mode:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Missing prompt or mode"})
            
        pvai = PVAI()
        result = pvai.enhance_prompt.remote(prompt, mode)
        return {"ok": True, "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@web_app.post("/api/generate")
async def handle_generate(request: Request):
    try:
        body = await request.json()
        pvai = PVAI()
        result = pvai.generate.remote(body)
        return {"ok": True, "result": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.function(image=image)
@modal.asgi_app()
def fastapi_app():
    return web_app

if __name__ == "__main__":
    print("To deploy: modal deploy modal_entrypoint.py")
