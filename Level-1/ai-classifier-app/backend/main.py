# main.py  FastAPI Application Entry Point
# ============================================
# Equivalent of Program.cs in .NET.
# App settings, middlewares, and endpoints are defined here.
#
# .NET comparison:
#   var builder = WebApplication.CreateBuilder(args);
#   builder.Services.AddCors(...);
#   var app = builder.Build();
#   app.MapPost("/api/classify", ...);
#   app.Run();

import asyncio
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from io import BytesIO

from classifier import classify_feedback
from config import settings
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from file_organizer import (
    OUTPUT_DIR,
    create_results_zip,
    delete_file,
    get_all_files,
    get_category_stats,
    move_file,
    organize_file,
    save_results_json,
)
from file_parser import extract_text, is_image_file, sanitize_filename, validate_file
from image_analyzer import extract_text_from_image
from models import (
    ClassificationRequest,
    ClassificationResponse,
    FileClassificationResponse,
    HealthResponse,
)
from prompt_manager import (
    build_system_prompt,
    get_default_config,
    load_config,
    reset_config,
    save_config,
)
from test_generator import generate_test_files

# -------------------------------------------------
# FastAPI Application Creation
# -------------------------------------------------
# .NET: var builder = WebApplication.CreateBuilder(args);
# Python: app = FastAPI(...)

app = FastAPI(
    title="AI Feedback Classifier",
    description="Automatically classifies customer feedback using AI",
    version="1.0.0",
)

# -------------------------------------------------
# CORS Middleware
# -------------------------------------------------
# Angular will send requests from localhost:4200.
# Without CORS, the browser blocks these requests.
#
# .NET equivalent:
#   builder.Services.AddCors(options =>
#       options.AddDefaultPolicy(policy =>
#           policy.WithOrigins("http://localhost:4200")
#                 .AllowAnyMethod()
#                 .AllowAnyHeader()));

# Build allowed origins list from environment variable
# ALLOWED_ORIGINS can be comma-separated: "https://myapp.pages.dev,http://localhost:4200"
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [
    origin.strip() for origin in _origins_env.split(",") if origin.strip()
]
if not _allowed_origins:
    _allowed_origins = ["http://localhost:4200"]  # Default for local dev

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# Endpoints
# -------------------------------------------------


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Verifies the backend is running and the API key is configured.

    .NET equivalent: app.MapGet("/api/health", () => new { Status = "ok" });
    """
    api_key_set = bool(settings.openai_api_key or settings.use_azure)
    return HealthResponse(
        status="ok" if api_key_set else "missing_api_key",
        model=settings.openai_model,
    )


@app.post("/api/classify", response_model=ClassificationResponse)
async def classify(request: ClassificationRequest):
    """
    Customer feedback classification endpoint.

    Flow:
    1. ClassificationRequest arrives from Angular (Pydantic auto-validates)
    2. The function in classifier.py sends a request to OpenAI
    3. Result is returned as ClassificationResponse

    .NET equivalent:
    app.MapPost("/api/classify", async (ClassificationRequest req) =>
    {
        var result = await _classifier.ClassifyAsync(req.Text);
        return Results.Ok(result);
    });
    """
    try:
        result = await classify_feedback(request.text)
        return result
    except Exception as e:
        # Return a meaningful error message
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during classification: {str(e)}",
        ) from e


@app.post("/api/classify-text")
async def classify_text(request: ClassificationRequest):
    """
    Classify text AND save it as a .txt file in output/{Category}/.

    Flow:
    1. Classify the text via OpenAI
    2. Generate a filename from the first words of the text + timestamp
    3. Save the text content as a .txt file in the appropriate category folder
    4. Return classification result + saved filename
    """
    try:
        result = await classify_feedback(request.text)

        # Generate a readable filename from the text
        words = re.sub(r"[^\w\s]", "", request.text).split()
        slug = "_".join(words[:5]).lower() or "feedback"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{slug}_{timestamp}.txt"

        # Save text as .txt file in output/{Category}/
        content_bytes = request.text.encode("utf-8")
        organize_file(filename, content_bytes, result.category)

        return {
            "classification": {
                "category": result.category,
                "sentiment": result.sentiment,
                "confidence": result.confidence,
                "summary": result.summary,
                "suggestions": result.suggestions,
            },
            "saved_filename": filename,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during classification: {str(e)}",
        ) from e


@app.post("/api/classify-file", response_model=FileClassificationResponse)
async def classify_file(file: UploadFile):
    """
    Classify customer feedback from an uploaded file.

    Flow:
    1. Validate file type and size
    2. Extract text (PDF/DOCX/TXT → text parser, images → GPT Vision)
    3. Send extracted text to OpenAI for classification
    4. Return filename + extracted text + classification result

    Supported formats: .pdf, .txt, .docx, .jpg, .jpeg, .png
    """
    # Read file content
    content = await file.read()
    filename = sanitize_filename(file.filename or "unnamed_file")

    # Validate file type and size
    error = validate_file(filename, file.content_type, len(content))
    if error:
        raise HTTPException(status_code=400, detail=error)

    try:
        # Extract text based on file type
        if is_image_file(filename):
            # Images → GPT Vision API (much better than OCR)
            extracted_text = await extract_text_from_image(filename, content)
        else:
            # PDF, DOCX, TXT → text extraction
            extracted_text = await extract_text(filename, content)

        # Classify the extracted text
        classification = await classify_feedback(extracted_text)

        return FileClassificationResponse(
            filename=filename,
            extracted_text=extracted_text,
            classification=classification,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred processing '{filename}': {str(e)}",
        ) from e


MAX_BATCH_FILES = 20


@app.post("/api/classify-files")
async def classify_files(files: list[UploadFile]):
    """
    Classify multiple files with real-time progress via SSE.

    Returns a Server-Sent Events stream. Each event:
    - type "progress": { index, total, filename, result?, error? }
    - type "complete": { results, errors, summary }

    Files are organized into output/Category/ folders with dedup.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files: {len(files)}. Max: {MAX_BATCH_FILES}",
        )

    # Pre-read all files into memory (UploadFile can't be read in generator)
    file_data: list[tuple[str, bytes, str | None]] = []
    for file in files:
        content = await file.read()
        filename = sanitize_filename(file.filename or "unnamed_file")
        file_data.append((filename, content, file.content_type))

    async def event_stream():
        total = len(file_data)
        results: list[FileClassificationResponse] = []
        errors: list[str] = []
        category_counts: dict[str, int] = {}

        for idx, (filename, content, content_type) in enumerate(file_data):
            # Validate
            validation_error = validate_file(filename, content_type, len(content))
            if validation_error:
                errors.append(f"{filename}: {validation_error}")
                event = {
                    "index": idx,
                    "total": total,
                    "filename": filename,
                    "error": validation_error,
                }
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"
                continue

            try:
                # Extract text
                if is_image_file(filename):
                    extracted_text = await extract_text_from_image(filename, content)
                else:
                    extracted_text = await extract_text(filename, content)

                # Classify
                classification = await classify_feedback(extracted_text)

                file_result = FileClassificationResponse(
                    filename=filename,
                    extracted_text=extracted_text,
                    classification=classification,
                )
                results.append(file_result)

                # Organize file into category folder
                organize_file(filename, content, classification.category)

                # Count categories
                cat = classification.category
                category_counts[cat] = category_counts.get(cat, 0) + 1

                event = {
                    "index": idx,
                    "total": total,
                    "filename": filename,
                    "result": {
                        "filename": file_result.filename,
                        "extracted_text": file_result.extracted_text,
                        "classification": {
                            "category": classification.category,
                            "sentiment": classification.sentiment,
                            "confidence": classification.confidence,
                            "summary": classification.summary,
                            "suggestions": classification.suggestions,
                        },
                    },
                }
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"

            except (ValueError, RuntimeError, OSError) as e:
                errors.append(f"{filename}: {str(e)}")
                event = {
                    "index": idx,
                    "total": total,
                    "filename": filename,
                    "error": str(e),
                }
                yield f"event: progress\ndata: {json.dumps(event)}\n\n"

        # Save cumulative results.json
        if results:
            save_results_json(results)

        # Final complete event
        complete = {
            "results": [
                {
                    "filename": r.filename,
                    "extracted_text": r.extracted_text,
                    "classification": {
                        "category": r.classification.category,
                        "sentiment": r.classification.sentiment,
                        "confidence": r.classification.confidence,
                        "summary": r.classification.summary,
                        "suggestions": r.classification.suggestions,
                    },
                }
                for r in results
            ],
            "errors": errors,
            "summary": category_counts,
        }
        yield f"event: complete\ndata: {json.dumps(complete)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/download-results")
async def download_results():
    """
    Download organized classification results as a ZIP file.

    The ZIP contains:
    - Category folders (Complaint/, Praise/, etc.) with original files
    - results.json summary
    """
    try:
        zip_bytes = create_results_zip()
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": ('attachment; filename="classified-results.zip"')
            },
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="No classified files found"
        ) from exc


@app.get("/api/category-stats")
async def category_stats():
    """Return file count per category folder."""
    return get_category_stats()


@app.get("/api/files")
async def list_files():
    """List all classified files with their category and size."""
    return get_all_files()


@app.delete("/api/files/{category}/{filename}")
async def remove_file(category: str, filename: str):
    """Delete a file from a category folder."""
    if delete_file(category, filename):
        return {"status": "deleted", "filename": filename}
    raise HTTPException(
        status_code=404, detail=f"File '{filename}' not found in {category}"
    )


@app.get("/api/files/{category}/{filename}/preview")
async def preview_file(category: str, filename: str):
    """Return text preview of a file from a category folder."""
    file_path = os.path.join(OUTPUT_DIR, category, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    with open(file_path, "rb") as f:
        content = f.read()

    # Extract text based on file type
    if is_image_file(filename):
        text = await extract_text_from_image(filename, content)
    else:
        text = await extract_text(filename, content)

    return {
        "filename": filename,
        "category": category,
        "size": len(content),
        "text": text or "(No text content could be extracted)",
    }


@app.post("/api/files/bulk-delete")
async def bulk_delete_files(items: list[dict]):
    """Delete multiple files at once. Each item: {category, filename}."""
    deleted = []
    failed = []
    for item in items:
        cat = item.get("category", "")
        name = item.get("filename", "")
        if delete_file(cat, name):
            deleted.append(name)
        else:
            failed.append(name)
    return {"deleted": deleted, "failed": failed}


@app.post("/api/files/move")
async def move_file_endpoint(
    filename: str,
    from_category: str,
    to_category: str,
):
    """Move a file from one category to another."""
    if move_file(filename, from_category, to_category):
        return {
            "status": "moved",
            "filename": filename,
            "from": from_category,
            "to": to_category,
        }
    raise HTTPException(
        status_code=400,
        detail=f"Cannot move '{filename}' from {from_category} to {to_category}",
    )


@app.post("/api/generate-test-files")
async def generate_test_files_endpoint(count: int = 40):
    """
    Generate random test files (TXT, PDF, DOCX) across all categories.
    Returns a ZIP file for browser download — nothing is saved to disk.
    """
    if count < 1 or count > 100:
        raise HTTPException(
            status_code=400,
            detail="Count must be between 1 and 100.",
        )
    try:
        files = generate_test_files(count)
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, category, content in files:
                zf.writestr(f"{category}/{filename}", content)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=test-files.zip"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate test files: {str(e)}",
        ) from e


# -------------------------------------------------
# Prompt Configuration Endpoints
# -------------------------------------------------


@app.get("/api/prompt-config")
async def get_prompt_config():
    """
    Get the current prompt configuration variables.
    Returns both the config and the generated system prompt preview.
    """
    config = load_config()
    return {
        "config": config,
        "preview": build_system_prompt(config),
        "is_default": config == get_default_config(),
    }


@app.put("/api/prompt-config")
async def update_prompt_config(body: dict):
    """
    Update prompt configuration variables.
    Validates required fields before saving.
    """
    required = ["role", "task", "response_language", "categories", "sentiments"]
    for field in required:
        if field not in body:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {field}",
            )

    if not isinstance(body.get("categories"), list) or len(body["categories"]) < 1:
        raise HTTPException(status_code=400, detail="At least one category is required")
    if not isinstance(body.get("sentiments"), list) or len(body["sentiments"]) < 1:
        raise HTTPException(
            status_code=400, detail="At least one sentiment is required"
        )

    save_config(body)
    config = load_config()
    return {
        "config": config,
        "preview": build_system_prompt(config),
        "is_default": config == get_default_config(),
    }


@app.post("/api/prompt-config/reset")
async def reset_prompt_config():
    """Reset prompt configuration to defaults."""
    config = reset_config()
    return {
        "config": config,
        "preview": build_system_prompt(config),
        "is_default": True,
    }


@app.get("/api/prompt-config/default")
async def get_default_prompt_config():
    """Get the default prompt configuration for comparison."""
    config = get_default_config()
    return {
        "config": config,
        "preview": build_system_prompt(config),
    }


@app.get("/api/files/watch")
async def watch_files():
    """
    SSE endpoint for real-time file system change notifications.

    Uses polling (every 2 seconds) to detect changes in the output/
    directory. Unlike watchfiles, this does NOT hold any directory
    handles open, avoiding Windows WinError 32 file locking issues.

    When files are added, modified, or deleted — even manually via
    Windows Explorer — the frontend receives a 'change' event and
    refreshes its file list.
    """

    def _snapshot() -> set[tuple[str, float]]:
        """Build a snapshot of (filepath, mtime) for all files in output/."""
        result = set()
        if not os.path.isdir(OUTPUT_DIR):
            return result
        for root, _dirs, files in os.walk(OUTPUT_DIR):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    result.add((fpath, os.path.getmtime(fpath)))
                except OSError:
                    pass
        return result

    async def event_stream():
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        yield "event: connected\ndata: {}\n\n"

        prev = _snapshot()
        while True:
            await asyncio.sleep(2)
            curr = _snapshot()
            if curr != prev:
                diff = len(curr.symmetric_difference(prev))
                prev = curr
                yield f"event: change\ndata: {json.dumps({'count': diff})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# -------------------------------------------------
# Application Startup Notes
# -------------------------------------------------
# To run this file directly:
#   uvicorn main:app --reload --port 8000
#
# --reload: Auto-restarts on code changes (hot reload)
#           Similar to dotnet watch run in .NET
#
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
