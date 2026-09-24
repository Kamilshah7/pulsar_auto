"""
FastAPI server for the Pulsar Audio Annotation Automation GUI.
"""
import os
import json
import webbrowser
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware

from pipeline import pipeline, BASE_DIR, OUTPUT_DIR

app = FastAPI(title="Pulsar Audio Automation Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class StartRequest(BaseModel):
    task_url: str

class LLMSubmitRequest(BaseModel):
    llm_output: str

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Pulsar Automation Studio GUI</h1><p>static/index.html not found.</p>"

@app.get("/api/status")
async def get_status():
    return JSONResponse(pipeline.get_state())

@app.post("/api/start")
async def start_task(req: StartRequest):
    url = req.task_url.strip()
    if not url.startswith("http"):
        return JSONResponse({"ok": False, "error": "Invalid URL provided."}, status_code=400)
    pipeline.start_pipeline_async(url)
    return JSONResponse({"ok": True, "message": "Pipeline started."})

@app.post("/api/auth-done")
async def signal_auth():
    pipeline.signal_auth_complete()
    return JSONResponse({"ok": True, "message": "Auth signal received."})

@app.post("/api/submit-llm")
async def submit_llm(req: LLMSubmitRequest):
    print("\n>>> [API /api/submit-llm] Processing LLM response with Pre-Label-Independent Forced Aligner (Whisper + Wav2Vec2 CTC)...", flush=True)
    try:
        js_code = pipeline.process_llm_output_and_generate_injection(req.llm_output)
        return JSONResponse({
            "ok": True,
            "inject_script": js_code,
            "count": pipeline.state["tokens_count"],
            "acoustic_stats": pipeline.state.get("acoustic_stats", {})
        })
    except Exception as e:
        print(f">>> [API /api/submit-llm] ERROR: {e}", flush=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

@app.get("/api/use-baseline")
async def use_baseline():
    """Run ForcedAligner on Whisper words + micro-slices to build perfected acoustic baseline."""
    print("\n>>> [API /api/use-baseline] Running Forced Aligner on Whisper + Wav2Vec2 micro-slice baseline...", flush=True)
    try:
        js_code = pipeline.generate_acoustic_baseline()
        return JSONResponse({
            "ok": True,
            "inject_script": js_code,
            "count": pipeline.state["tokens_count"],
            "acoustic_stats": pipeline.state.get("acoustic_stats", {})
        })
    except Exception as e:
        print(f">>> [API /api/use-baseline] ERROR: {e}", flush=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/save-ground-truth")
async def save_ground_truth(req: Request):
    """Save user-perfected tokens as baseline_ground_truth.json."""
    try:
        data = await req.json()
        tokens = data.get("tokens", data) if isinstance(data, dict) else data
        if not isinstance(tokens, list):
            return JSONResponse({"ok": False, "error": "Expected a list of tokens."}, status_code=400)
        
        gt_path = os.path.join(OUTPUT_DIR, "baseline_ground_truth.json")
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)
        
        # Also backup a copy
        backup_path = os.path.join(OUTPUT_DIR, "user_perfected_ground_truth.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)
            
        print(f"\n>>> [API /api/save-ground-truth] SUCCESS: Saved {len(tokens)} perfected ground truth tokens to {gt_path}", flush=True)
        return JSONResponse({
            "ok": True,
            "message": f"Successfully saved {len(tokens)} perfected ground truth tokens.",
            "count": len(tokens),
            "file": gt_path
        })
    except Exception as e:
        print(f">>> [API /api/save-ground-truth] ERROR: {e}", flush=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

if __name__ == "__main__":
    port = 7860
    print(f"\n=======================================================")
    print(f"  PULSAR AUTOMATION STUDIO GUI")
    print(f"  Pre-Label-Independent Acoustic Engine (Whisper + Wav2Vec2 + ForcedAligner) LOADED")
    print(f"  Open in your browser: http://localhost:{port}")
    print(f"=======================================================\n")
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

