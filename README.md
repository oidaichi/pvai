# PVAI (Headless ComfyUI)

PVAI is a headless, cloud-native adaptation of ComfyUI designed for commercial video generation SaaS. It runs on Modal and integrates with Supabase for storage.

## Architecture

- **Platform**: Modal (Serverless GPU)
- **Storage**: Supabase Storage
- **Execution**: Headless (Request/Response model)
- **Models**: Nano Banana Pro, LongCat Video, LivePortrait

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Running on Modal

The main entry point is `modal_entrypoint.py`. It defines the `PVAI` class which warms up the environment and executes workflows.

```bash
modal run modal_entrypoint.py
```

### Headless API

The system provides a `generate` method that accepts a ComfyUI workflow (JSON) and parameter overrides.

```python
# Example Usage (pseudo-code)
pvai = PVAI()
result = pvai.generate.remote(workflow_json, params={"1": {"seed": 12345}})
```

### Workflow Templates

Pre-defined templates for specific use cases are located in `workflows/`:

- `case_a_influencer.json`: T2I with IP-Adapter (Nano Banana Pro).
- `case_b_lipsync.json`: Audio-driven animation (LivePortrait).
- `case_c_pose.json`: Video-to-Video with physics (LongCat).

## Custom Nodes

- `PVAI/IO`:
    - `LoadImageFromUrl`: Downloads images directly from a URL.
    - `SaveVideoToUpload`: Uploads generated video to Supabase and returns a signed URL.
- `PVAI/Models`:
    - `NanoBananaProT2I`: Wrapper for T2I generation with IP-Adapter support.
    - `LongCatVideoWrapper`: Wrapper for LongCat Video generation.
    - `LivePortraitNode`: Wrapper for LivePortrait lipsync.
- `PVAI/Audio`:
    - `AudioGeneration`: Generates audio from text prompt.

## Development

- **Middleware**: `middleware/workflow_patcher.py` handles dynamic parameter injection.
- **Mock Server**: `headless_server.py` mocks the ComfyUI WebSocket server for internal execution.
- **Tests**: Run `python -m unittest discover tests` to verify components.
