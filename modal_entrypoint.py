import modal
import sys
import os
import uuid
from typing import Dict, Any

def file_filter(p):
    # Convert Path object to string and normalize slashes
    p_str = str(p).replace("\\", "/")
    
    # Always ignore these
    if ".git" in p_str or "output" in p_str or "__pycache__" in p_str:
        return True
    
    # Special handling for 'models' folder
    if "models" in p_str:
        # If 'comfy' is in the path, it's likely source code (e.g. comfy/ldm/models)
        if "comfy" in p_str:
            return False
        # Otherwise, assume it's the heavy weights folder at root
        return True
        
    return False

# Define the image
# We install system dependencies for OpenCV and FFmpeg
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "libgl1-mesa-glx", "libglib2.0-0")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir(".", remote_path="/root/pvai", copy=True, ignore=file_filter) 
)
# Note: In newer modal versions, add_local_dir uses 'ignore' callback that returns True to ignore. 
# Or 'condition' if older? Let's verify API or try simple include.
# Actually, add_local_dir(local_path, remote_path, copy=True) copies everything. 
# We need to be careful not to copy huge models.

# Let's try to use explicit add_local_python_source or similar if available, 
# but add_local_dir is safest if we can filter.
# Since we don't know the exact API signature of add_local_dir filter in this version,
# let's try a safer approach: standard mount is implicitly handled for the script itself.
# But we need the whole folder structure.

# Let's check dir(modal.Image) to see available methods.


app = modal.App("pvai-engine", image=image)

# Persistent volume for models
models_volume = modal.Volume.from_name("pvai-models", create_if_missing=True)

@app.cls(
    gpu="A10G", 
    min_containers=1, 
    timeout=600,
    volumes={"/root/vol_models": models_volume}
)
class PVAI:
    def __init__(self):
        self.execution = None
        self.server = None
        self.executor = None

    def initialize(self):
        """
        Initialize ComfyUI and load models.
        """
        print("DEBUG: Initializing PVAI Engine...")
        project_path = "/root/pvai"
        models_path = os.path.join(project_path, "models")
        vol_path = "/root/vol_models"

        # Debug: Check file structure
        print(f"Project Path: {project_path}")
        
        if project_path not in sys.path:
            sys.path.append(project_path)
            
        # Change working directory so ComfyUI finds its config
        os.chdir(project_path)

        # Setup Models Volume Link
        # If models dir exists (from add_local_dir), we replace it with symlink to volume
        if os.path.exists(models_path):
            if os.path.islink(models_path):
                os.remove(models_path)
            elif os.path.isdir(models_path):
                import shutil
                shutil.rmtree(models_path)
        
        # Create symlink: models -> /root/vol_models
        if not os.path.exists(models_path):
            os.symlink(vol_path, models_path)
            print(f"Linked {models_path} -> {vol_path}")
        
        # Import ComfyUI modules (lazy import inside container)
        try:
            # Ensure path is set for imports
            if project_path not in sys.path:
                sys.path.insert(0, project_path)

            import folder_paths
            import execution
            from headless_server import HeadlessServer
            import nodes
            
            self.execution = execution
            self.server = HeadlessServer()
            self.executor = execution.PromptExecutor(self.server)
            
            # Load custom nodes
            # This scans 'custom_nodes' folder and imports them
            import asyncio
            # Use asyncio.run to execute the async init function
            asyncio.run(nodes.init_extra_nodes())
            
            print("PVAI Engine Initialized.")
            
        except ImportError as e:
            print(f"Initialization Error: {e}")
            # Debug sys.path
            print(f"sys.path: {sys.path}")
            raise e
        except Exception as e:
            print(f"Runtime Error during init: {e}")
            raise e

    def __enter__(self):
        """
        Warmup routine: Initializes ComfyUI and loads models into memory.
        """
        print("DEBUG: __enter__ CALLED")
        self.initialize()

    @modal.method()
    def generate(self, workflow_json: Dict[str, Any], params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Headless generation entry point.
        """
        import asyncio
        
        # Ensure initialization
        if self.execution is None:
            print("WARNING: self.execution is None in generate. Calling initialize().")
            self.initialize()

        # Ensure path is present in runtime
        project_path = "/root/pvai"
        if project_path not in sys.path:
            sys.path.append(project_path)

        # Debug: Check file system structure in generate method
        print(f"Generate called. Checking structure of {project_path}")
        if os.path.exists(project_path):
            for root, dirs, files in os.walk(project_path):
                print(f"Dir: {root}, Files: {files}")
        else:
            print(f"CRITICAL: {project_path} does not exist inside generate!")

        try:
            from middleware.workflow_patcher import patch_workflow
        except ImportError:
            print(f"ImportError: middleware not found. sys.path: {sys.path}")
            raise
        
        prompt_id = str(uuid.uuid4())
        
        print(f"Starting generation for Prompt ID: {prompt_id}")
        
        # 1. Patch Workflow
        if params:
            print("Patching workflow with params...")
            workflow_json = patch_workflow(workflow_json, params)
            
        # 2. Validate Workflow
        print("Validating workflow...")
        
        # validate_prompt is async and takes (prompt_id, prompt, partial_execution_list)
        try:
            valid, error, outputs, _ = asyncio.run(self.execution.validate_prompt(prompt_id, workflow_json, None))
        except Exception as e:
             print(f"Validation failed with exception: {e}")
             raise e

        if not valid:
            error_msg = f"Invalid workflow: {error}"
            print(error_msg)
            raise ValueError(error_msg)
            
        # 3. Execute
        # Reset server outputs capture for this run
        self.server.outputs = {}
        
        # This is blocking/synchronous in the prompt executor
        print("Executing workflow...")
        try:
            self.executor.execute(workflow_json, prompt_id)
        except Exception as e:
            print(f"Execution failed: {e}")
            raise e
        
        print("Execution complete.")
        
        # 4. Return results
        return self.server.outputs

    @modal.method()
    def concat_videos(self, video_urls: list[str]) -> str:
        """
        Downloads multiple videos, concatenates them using ffmpeg, and uploads the result.
        
        Args:
            video_urls: List of signed URLs to the video parts.
            
        Returns:
            Signed URL of the concatenated video.
        """
        import ffmpeg
        import requests
        import uuid
        import os
        
        # We need to import Supabase client here again or make it global/class member
        try:
            from supabase import create_client
            SUPABASE_AVAILABLE = True
        except ImportError:
            SUPABASE_AVAILABLE = False
            print("Supabase not available for concat")
            return "error_no_supabase"

        print(f"Concatenating {len(video_urls)} videos...")
        
        temp_files = []
        try:
            # 1. Download all videos
            for i, url in enumerate(video_urls):
                local_filename = f"/tmp/part_{i}_{uuid.uuid4()}.mp4"
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(local_filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                temp_files.append(local_filename)
            
            # 2. Concat using ffmpeg-python
            # Create a file list for ffmpeg concat demuxer
            list_file_path = f"/tmp/concat_list_{uuid.uuid4()}.txt"
            with open(list_file_path, 'w') as f:
                for tf in temp_files:
                    f.write(f"file '{tf}'\n")
            
            output_path = f"/tmp/final_{uuid.uuid4()}.mp4"
            
            (
                ffmpeg
                .input(list_file_path, format='concat', safe=0)
                .output(output_path, c='copy')
                .run(overwrite_output=True, quiet=True)
            )
            
            # 3. Upload Result
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            
            if not url or not key:
                print("Supabase credentials missing.")
                return output_path # Return local path in dev/test if env missing
            
            supabase = create_client(url, key)
            bucket = "videos"
            final_filename = f"assembly_{uuid.uuid4()}.mp4"
            
            with open(output_path, 'rb') as f:
                supabase.storage.from_(bucket).upload(final_filename, f)
                
            res = supabase.storage.from_(bucket).create_signed_url(final_filename, 3600)
            
            # Cleanup
            if os.path.exists(list_file_path): os.remove(list_file_path)
            if os.path.exists(output_path): os.remove(output_path)
            for tf in temp_files:
                if os.path.exists(tf): os.remove(tf)
                
            if 'signedURL' in res:
                return res['signedURL']
            return str(res)
            
        except Exception as e:
            print(f"Concat failed: {e}")
            raise e

import json

# Local testing entry point
@app.local_entrypoint()
def test_run(workflow_path: str = "workflows/case_b_lipsync.json"):
    """
    Run a test workflow on Modal.
    Usage: modal run modal_entrypoint.py --workflow-path workflows/case_b_lipsync.json
    """
    print(f"Loading workflow from: {workflow_path}")
    
    try:
        with open(workflow_path, "r") as f:
            workflow = json.load(f)
    except FileNotFoundError:
        print(f"Error: Workflow file not found: {workflow_path}")
        return

    # Instantiate the remote class
    print("Initializing remote PVAI engine...")
    pvai = PVAI()

    # Define test parameters
    # Case A: {"1": {"seed": 12345}}
    # Case B: {"2": {"prompt": "Hello world from Modal cloud test!"}}
    
    if "case_a" in workflow_path:
        params = {"1": {"seed": 12345}}
    elif "case_b" in workflow_path:
        params = {"2": {"prompt": "Hello world from Modal cloud test!"}}
    elif "case_c" in workflow_path:
        params = {"2": {"motion_scale": 1.2}}
    else:
        params = {}

    print(f"Sending generation request with params: {params}")
    try:
        # Call the remote method
        result = pvai.generate.remote(workflow, params)
        print("\n--- Generation Result ---")
        print(json.dumps(result, indent=2))
        print("-------------------------")
    except Exception as e:
        print(f"\nError during remote execution: {e}")

if __name__ == "__main__":
    # This allows running 'python modal_entrypoint.py' to see usage info, 
    # though 'modal run' is the intended way.
    print("Please run this using: modal run modal_entrypoint.py")
