import os
import json
import asyncio
from aiohttp import web
from typing import Dict, Any

def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_workflow(mode):
    base = os.path.join(os.getcwd(), "workflows")
    if mode == "case_a":
        return json.loads(read_text(os.path.join(base, "case_a_influencer.json")))
    if mode == "case_b":
        return json.loads(read_text(os.path.join(base, "case_b_lipsync.json")))
    if mode == "case_c":
        return json.loads(read_text(os.path.join(base, "case_c_pose.json")))
    raise web.HTTPBadRequest(text="unknown mode")

def build_params(mode, payload: Dict[str, Any]):
    p = {}
    if mode == "case_a":
        p["1"] = {}
        if "prompt" in payload: p["1"]["prompt"] = payload["prompt"]
        if "seed" in payload: p["1"]["seed"] = int(payload["seed"])
        if "steps" in payload: p["1"]["steps"] = int(payload["steps"])
        if "ip_adapter_weight" in payload: p["1"]["ip_adapter_weight"] = float(payload["ip_adapter_weight"])
        if "ip_adapter_image" in payload: p["10"] = {"url": payload["ip_adapter_image"]}
    elif mode == "case_b":
        if "character_image" in payload: p["1"] = {"url": payload["character_image"]}
        p["2"] = {}
        if "audio_prompt" in payload: p["2"]["prompt"] = payload["audio_prompt"]
        if "duration" in payload: p["2"]["duration"] = float(payload["duration"])
        if "expression_mode" in payload: p["3"] = {"expression_mode": payload["expression_mode"]}
    elif mode == "case_c":
        if "reference_image" in payload: p["1"] = {"url": payload["reference_image"]}
        p["2"] = {}
        if "motion_scale" in payload: p["2"]["motion_scale"] = float(payload["motion_scale"])
        if "physics_bias" in payload: p["2"]["physics_bias"] = float(payload["physics_bias"])
        if "prompt" in payload: p["2"]["prompt"] = payload["prompt"]
    return p

async def handle_index(request):
    path = os.path.join(os.getcwd(), "index.html")
    return web.Response(text=read_text(path), content_type="text/html; charset=utf-8")

async def handle_generate(request):
    try:
        body = await request.json()
    except:
        raise web.HTTPBadRequest(text="invalid json")
    mode = body.get("mode")
    payload = body.get("payload", {})
    director_json = body.get("director_json")
    workflow = load_workflow(mode)
    params = build_params(mode, payload)
    if director_json:
        try:
            dj = json.loads(director_json)
        except:
            dj = None
        if dj is not None:
            params["director"] = dj
    try:
        from modal_entrypoint import PVAI
        pvai = PVAI()
        result = pvai.generate.remote(workflow, params)
        return web.json_response({"ok": True, "result": result})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)

async def handle_concat(request):
    try:
        body = await request.json()
    except:
        raise web.HTTPBadRequest(text="invalid json")
    urls = body.get("urls", [])
    if not isinstance(urls, list) or len(urls) == 0:
        raise web.HTTPBadRequest(text="urls required")
    try:
        from modal_entrypoint import PVAI
        pvai = PVAI()
        url = pvai.concat_videos.remote(urls)
        return web.json_response({"ok": True, "url": url})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500)

def create_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_post("/api/generate", handle_generate)
    app.router.add_post("/api/concat", handle_concat)
    return app

def main():
    app = create_app()
    web.run_app(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()
