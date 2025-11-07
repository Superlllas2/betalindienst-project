"""
Betalindienst Fraud Check backend implemented with FastAPI.
Run locally with:
    uvicorn app:app --reload --port 8000
"""

import hashlib
import mimetypes
import random
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Instantiate the FastAPI application.
app = FastAPI(title="Betalindienst Fraud Check API")

# Configure CORS so the Vue frontend (running on localhost:5173) can access the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the set of allowed file extensions. All other types will be rejected.
ALLOWED_EXTENSIONS = {
    ".jpeg",
    ".jpg",
    ".png",
    ".csv",
    ".txt",
    ".pdf",
    ".xif",
    ".log",
    ".json",
}

# Set a maximum file size of 50 MB for accepted files.
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024


def _get_extension(filename: str) -> str:
    """Return the lowercase file extension (including the dot)."""
    return Path(filename).suffix.lower()


def _detect_mime_type(filename: str) -> str:
    """Best-effort MIME type detection using Python's mimetypes module."""
    guessed_type, _ = mimetypes.guess_type(filename)
    return guessed_type or "application/octet-stream"


def _calculate_fraud_score_stub(file_bytes: bytes) -> float:
    """
    Generate a deterministic yet fake fraud score by hashing the file contents.

    Taking the SHA256 digest ensures the score is reproducible for the same file
    while still resembling randomness.
    """
    if not file_bytes:
        return random.random()

    digest = hashlib.sha256(file_bytes).hexdigest()
    # Convert the first 15 characters of the hex digest to an integer and normalize.
    numeric_value = int(digest[:15], 16)
    return (numeric_value % 1_000_000) / 1_000_000


@app.post("/api/check")
async def check_files(files: List[UploadFile] = File(...)) -> JSONResponse:
    """
    Accept multiple uploaded files and return metadata describing whether each
    file is allowed, rejected, and why.
    """

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    processed_files = []
    first_allowed_file_bytes: Optional[bytes] = None

    for upload in files:
        extension = _get_extension(upload.filename or "")
        mime_type = _detect_mime_type(upload.filename or "")
        allowed = extension in ALLOWED_EXTENSIONS
        reasons: List[str] = []
        if not allowed:
            reasons.append("unsupported_type")
        else:
            # Read the entire file content into memory.
            file_bytes = await upload.read()
            file_size = len(file_bytes)

            if file_size > MAX_FILE_SIZE_BYTES:
                allowed = False
                reasons.append("file_too_large")
            else:
                reasons.append("accepted")
                if first_allowed_file_bytes is None:
                    # Store bytes of the first valid file to generate the fraud score later.
                    first_allowed_file_bytes = file_bytes

        processed_files.append(
            {
                "filename": upload.filename,
                "extension": extension,
                "mime_type": mime_type,
                "allowed": allowed,
                "reasons": reasons,
            }
        )

        # Release resources associated with the uploaded file.
        await upload.close()

    total_files = len(processed_files)
    accepted_files = sum(1 for file_info in processed_files if file_info["allowed"])
    rejected_files = total_files - accepted_files

    # Produce a single fraud score using the first accepted file if available,
    # otherwise fall back to a random score.
    if processed_files and accepted_files and first_allowed_file_bytes is not None:
        fraud_score = _calculate_fraud_score_stub(first_allowed_file_bytes)
    else:
        fraud_score = random.random()

    response_payload = {
        "summary": {
            "total": total_files,
            "accepted": accepted_files,
            "rejected": rejected_files,
            "fraud_score_stub": fraud_score,
        },
        "files": processed_files,
    }

    return JSONResponse(content=response_payload)
