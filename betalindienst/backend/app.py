"""FastAPI application for the Betalindienst Fraud Sentinel demo."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from analysis import analyzers


LOGGER = logging.getLogger("betalindienst.backend")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = BASE_DIR / "uploads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

app = FastAPI(title="Betalindienst Fraud Sentinel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)) -> JSONResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    files_meta = []

    for upload in files:
        meta = {
            "filename": upload.filename or "unnamed",
            "size": 0,
            "mimetype": upload.content_type or "application/octet-stream",
            "analysis": None,
            "rejected_reason": None,
        }

        data = await upload.read()
        size = len(data)
        meta["size"] = size

        if size > MAX_FILE_SIZE:
            meta["rejected_reason"] = "file_too_large"
            files_meta.append(meta)
            LOGGER.warning("File %s rejected: exceeds size limit", meta["filename"])
            continue

        safe_name = (Path(meta["filename"]).name or "file").replace(" ", "_")
        stored_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        file_path = job_dir / stored_name

        with open(file_path, "wb") as buffer:
            buffer.write(data)

        meta["stored_name"] = stored_name
        meta["path"] = file_path

        suffix = file_path.suffix.lower()
        if suffix in {".csv", ".json"}:
            analyzed, reason, analysis = analyzers.analyze_file(file_path, suffix)
            if analyzed and analysis:
                meta["analysis"] = analysis
            else:
                meta["rejected_reason"] = reason
        else:
            meta["rejected_reason"] = "not_analyzed"

        files_meta.append(meta)

    result = analyzers.build_result(job_id, files_meta)

    result_path = job_dir / "result.json"
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    LOGGER.info("Job %s processed with %d files", job_id, len(files_meta))
    return JSONResponse({"job_id": job_id})


@app.get("/api/result/{job_id}")
async def get_result(job_id: str) -> JSONResponse:
    job_dir = UPLOAD_ROOT / job_id
    result_path = job_dir / "result.json"

    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Job not found or still processing")

    with open(result_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return JSONResponse(payload)


@app.get("/api/health")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok"})
