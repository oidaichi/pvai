from typing import Dict, Any

def patch_workflow(workflow: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Patches a ComfyUI workflow (API format) with dynamic parameters.
    
    Args:
        workflow (Dict[str, Any]): The base workflow in ComfyUI API format (key=node_id, value=node_data).
        params (Dict[str, Any]): A dictionary of parameters to inject. 
                                 Format: { node_id: { input_name: value } }
    
    Returns:
        Dict[str, Any]: The patched workflow.
    """
    import copy
    patched = copy.deepcopy(workflow)
    
    for node_id, updates in params.items():
        if node_id in patched:
            if "inputs" not in patched[node_id]:
                patched[node_id]["inputs"] = {}
            
            for key, value in updates.items():
                patched[node_id]["inputs"][key] = value
        else:
            # Optional: Log warning if node_id not found?
            # For now, we ignore invalid node_ids or assume they might be meta-data
            pass
            
    return patched
