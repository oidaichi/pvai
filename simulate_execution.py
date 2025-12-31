import sys
import os
import json
from unittest.mock import MagicMock

# ---------------------------------------------------------
# 1. Setup Mocks for Missing Dependencies
# ---------------------------------------------------------
print("[System] Setting up mock environment for demonstration...")

# Mock torch
mock_torch = MagicMock()
mock_torch.Tensor = MagicMock
mock_torch.from_numpy = lambda x: x
mock_torch.zeros = lambda *args, **kwargs: "Tensor(Zeros)"
sys.modules["torch"] = mock_torch

# Mock numpy
mock_numpy = MagicMock()
mock_numpy.array = lambda x: x
mock_numpy.float32 = "float32"
mock_numpy.uint8 = "uint8"
sys.modules["numpy"] = mock_numpy

# Mock PIL
mock_pil = MagicMock()
mock_pil.Image = MagicMock()
mock_pil.Image.open = lambda x: MagicMock()
mock_pil.ImageOps = MagicMock()
sys.modules["PIL"] = mock_pil

# Mock requests
mock_requests = MagicMock()
mock_response = MagicMock()
mock_response.content = b"fake_image_bytes"
mock_requests.get.return_value = mock_response
sys.modules["requests"] = mock_requests

# Mock supabase
mock_supabase = MagicMock()
mock_client = MagicMock()
mock_client.storage.from_().upload.return_value = None
mock_client.storage.from_().create_signed_url.return_value = {"signedURL": "https://supabase.co/storage/v1/object/sign/videos/generated.mp4"}
mock_supabase.create_client.return_value = mock_client
sys.modules["supabase"] = mock_supabase

# Mock av (PyAV)
mock_av = MagicMock()
sys.modules["av"] = mock_av

# Mock folder_paths (ComfyUI internal)
mock_folder_paths = MagicMock()
mock_folder_paths.get_temp_directory.return_value = "/tmp/comfy_temp"
sys.modules["folder_paths"] = mock_folder_paths

# Mock modal
sys.modules["modal"] = MagicMock()

print("[System] Mocks initialized.\n")

# ---------------------------------------------------------
# 2. Import System Components
# ---------------------------------------------------------
# Add current directory to path
sys.path.append(os.getcwd())

from middleware.workflow_patcher import patch_workflow
from headless_server import HeadlessServer

# Import Custom Nodes
# We manually import them to simulate ComfyUI's loading process
from custom_nodes.pvai_nodes.nodes import LoadImageFromUrl, SaveVideoToUpload
from custom_nodes.NanoBananaPro.nodes import NanoBananaProT2I
from custom_nodes.LongCat_Wrapper.nodes import LongCatVideoWrapper
from custom_nodes.pvai_nodes.audio_nodes import AudioGeneration
from custom_nodes.LivePortrait_Wrapper.nodes import LivePortraitNode

# Node Registry
NODE_REGISTRY = {
    "LoadImageFromUrl": LoadImageFromUrl,
    "SaveVideoToUpload": SaveVideoToUpload,
    "NanoBananaProT2I": NanoBananaProT2I,
    "LongCatVideoWrapper": LongCatVideoWrapper,
    "AudioGeneration": AudioGeneration,
    "LivePortraitNode": LivePortraitNode
}

# ---------------------------------------------------------
# 3. Simulation Logic
# ---------------------------------------------------------

def simulate_workflow_execution(workflow_file, params, scenario_name):
    print(f"--- Starting Simulation: {scenario_name} ---")
    
    # 1. Load Workflow
    print(f"[1] Loading workflow from: {workflow_file}")
    with open(workflow_file, 'r') as f:
        workflow = json.load(f)
    
    # 2. Patch Workflow (Middleware)
    print(f"[2] Applying middleware patch...")
    print(f"    Params: {params}")
    patched_workflow = patch_workflow(workflow, params)
    
    # 3. Execution Simulation
    # Since we don't have the full ComfyUI execution engine running, 
    # we will topologically sort (manually for this demo) and execute the nodes.
    print(f"[3] Executing nodes...")
    
    # Storage for node outputs: {node_id: output_tuple}
    outputs = {}
    
    # Simple Topological Sort Simulation based on known dependencies for the demo cases
    # We look for nodes and execute them in logical order
    # For a real implementation, we would build a graph and sort.
    # Here, we know the IDs are generally numeric, but dependency order matters.
    # Case A: 10 -> 1 -> 20
    # Case B: 1, 2 -> 3 -> 20
    # Case C: 1 -> 2 -> 20
    # So sorting by ID numerically is risky if IDs are not ordered by dependency.
    # Let's do a simple multi-pass resolution.
    
    executed = set()
    node_ids = list(patched_workflow.keys())
    
    # Max passes to prevent infinite loop
    for _ in range(len(node_ids) + 1):
        progress = False
        for node_id in node_ids:
            if node_id in executed:
                continue
                
            node_data = patched_workflow[node_id]
            inputs = node_data["inputs"]
            
            # Check if all dependencies are met
            dependencies_met = True
            for v in inputs.values():
                if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                    dep_id = v[0]
                    if dep_id not in executed:
                        dependencies_met = False
                        break
            
            if dependencies_met:
                # Execute Node
                class_type = node_data["class_type"]
                title = node_data.get("_meta", {}).get("title", "Unknown")
                
                print(f"    -> Executing Node {node_id}: {title} ({class_type})")
                
                if class_type not in NODE_REGISTRY:
                    print(f"       [Warning] Node class {class_type} not found in registry. Skipping.")
                    executed.add(node_id) # Mark as executed to avoid loop, but output is missing
                    continue
                    
                node_instance = NODE_REGISTRY[class_type]()
                func_name = NODE_REGISTRY[class_type].FUNCTION
                func = getattr(node_instance, func_name)
                
                # Resolve Inputs
                resolved_inputs = {}
                for k, v in inputs.items():
                    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                        source_id = v[0]
                        slot_idx = v[1]
                        if source_id in outputs:
                            resolved_inputs[k] = outputs[source_id][slot_idx]
                            print(f"       Resolved input '{k}' from Node {source_id}")
                        else:
                            print(f"       [Error] Missing dependency output from Node {source_id}")
                            resolved_inputs[k] = None
                    else:
                        resolved_inputs[k] = v
                
                try:
                    result = func(**resolved_inputs)
                    outputs[node_id] = result
                    print(f"       Output: {result}")
                except Exception as e:
                    print(f"       [Error] Execution failed: {e}")
                    # For SaveVideoToUpload mock failure (tensor shape), let's fake it
                    if class_type == "SaveVideoToUpload":
                         print("       [Mock Recovery] Returning fake URL")
                         outputs[node_id] = ("https://mock-supabase.url/video.mp4",)
                
                executed.add(node_id)
                progress = True
        
        if not progress and len(executed) < len(node_ids):
            print("[Warning] Cyclic dependency or missing dependency detected. Stopping.")
            break

    print(f"--- Simulation Complete: {scenario_name} ---\n")

# ---------------------------------------------------------
# 4. Run Scenarios
# ---------------------------------------------------------

if __name__ == "__main__":
    # Scenario A: Influencer (T2I)
    simulate_workflow_execution(
        "workflows/case_a_influencer.json", 
        {"1": {"seed": 8888, "ip_adapter_weight": 0.9}}, 
        "Case A: Influencer"
    )

    # Scenario B: Lipsync
    simulate_workflow_execution(
        "workflows/case_b_lipsync.json",
        {"2": {"prompt": "Hello from the simulation script!"}},
        "Case B: Lipsync"
    )

    # Scenario C: Pose (V2V)
    simulate_workflow_execution(
        "workflows/case_c_pose.json",
        {"2": {"motion_scale": 1.2}},
        "Case C: Pose Control"
    )
