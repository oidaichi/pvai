# Performance & Optimization Report

## Cold Start vs Warm Start Analysis

### Standard Execution (Cold Start)
- **Process**: Docker container boot -> Python interpreter start -> Import modules -> Load Model Weights (Checkpoints, VAE, CLIP) from disk/network.
- **Estimated Time**: 
  - Container Boot: 2-5s
  - Model Load (SDXL/Flux): 10-30s (depending on disk I/O and VRAM transfer)
  - **Total Latency**: ~15-40s per request.

### Modal App.cls (Warm Start)
- **Process**: Container stays alive. Models are pre-loaded in GPU VRAM (`__enter__` method).
- **Estimated Time**:
  - Request Handling: <100ms
  - Inference: Pure GPU compute time (e.g., 2-5s for turbo models).
  - **Total Latency**: ~3-6s.

### Optimization Gains
- **Throughput**: 5x - 10x increase.
- **Cost**: Higher idle cost (paying for GPU uptime), but significantly lower per-image latency.

## Memory Management
- **Strategy**: `modal_entrypoint.py` initializes the executor once. ComfyUI's `model_management` caches models.
- **Risk**: VRAM fragmentation over time.
- **Mitigation**: Modal restarts container after `timeout=600` (10 mins) of inactivity or after N requests if configured, ensuring fresh state periodically.

## Recommendations for Production
1. **Model Storage**: Use `modal.Volume` or high-performance network storage (Supabase S3) for model weights to reduce cold start time further if container is recycled.
2. **Concurrency**: Enable `allow_concurrent_inputs` in Modal if the GPU has enough VRAM to batch requests, or scale out replicas.
3. **Monitoring**: Integrate Sentry or similar for tracking Python exceptions in the headless runner.
