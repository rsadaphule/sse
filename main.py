"""
Real-time build-log streaming with FastAPI + SSE.
Run with:  uvicorn backend.main:app --reload
"""

import asyncio, json, random, time, uuid
from typing import Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],          # POST, GET, OPTIONS, …
    allow_headers=["*"],          # Content-Type, Authorization, …
)



# --------------------------------------------------------------------------- #
# In-memory build registry (for demo only; swap for Redis/Kafka in production)
# --------------------------------------------------------------------------- #
class Build:
    """Holds an asyncio.Queue that receives log lines as they appear."""
    def __init__(self) -> None:
        self.id: str = uuid.uuid4().hex[:8]
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.finished: bool = False

    async def run(self) -> None:
        """Simulate a build that produces ~30 log lines."""
        steps = [
            "Cloning repository",
            "Installing dependencies",
            "Running tests",
            "Building assets",
            "Packaging artifacts",
            "Deploying to staging",
            "Smoke tests",
            "Deploying to production",
        ]
        for step in steps:
            await asyncio.sleep(random.uniform(0.6, 1.4))
            await self.queue.put(f"[{timestamp()}] ➜ {step} …")

            # Fake sub-logs
            for i in range(random.randint(1, 4)):
                await asyncio.sleep(random.uniform(0.1, 0.4))
                await self.queue.put(f"[{timestamp()}]     {step} — detail {i+1}")

            await self.queue.put(f"[{timestamp()}] ✓ {step} completed")

        self.finished = True
        await self.queue.put(f"[{timestamp()}] 🎉 Build {self.id} completed successfully")

def timestamp() -> str:
    return time.strftime("%H:%M:%S")

BUILDS: Dict[str, Build] = {}

# --------------------------------------------------------------------------- #
# REST API
# --------------------------------------------------------------------------- #
@app.post("/build/start", status_code=status.HTTP_201_CREATED)
async def start_build() -> JSONResponse:
    build = Build()
    BUILDS[build.id] = build
    # Fire-and-forget background task
    asyncio.create_task(build.run())
    return JSONResponse({"build_id": build.id})

@app.get("/build/{build_id}/stream")
async def stream_logs(build_id: str, request: Request) -> StreamingResponse:
    build = BUILDS.get(build_id)
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    async def event_generator():
        """Yield SSE-formatted chunks until build finishes and queue drains."""
        # Flush any “missed” lines first
        while True:
            try:
                line = build.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            yield format_sse(line)

        while not build.finished or not build.queue.empty():
            # Break early if client gone
            if await request.is_disconnected():
                break
            line = await build.queue.get()
            yield format_sse(line)

        # Close stream
        yield "event: done\ndata: {}\n\n"

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # nginx, some proxies
        "Access-Control-Allow-Origin": "*",  # CORS for dev
    }
    return StreamingResponse(event_generator(),
                             media_type="text/event-stream",
                             headers=headers)

def format_sse(data: str) -> str:
    """Convert a plain string into `data: …\\n\\n` format (no id/event here)."""
    return f"data: {json.dumps(data)}\n\n"
