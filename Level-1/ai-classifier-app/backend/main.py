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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from classifier import classify_feedback
from config import settings
from models import ClassificationRequest, ClassificationResponse, HealthResponse

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",  # Angular dev server
    ],
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
