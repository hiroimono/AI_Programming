# image_analyzer.py — Image Analysis via GPT Vision API
# ========================================================
# Sends images directly to GPT-4o-mini Vision API for analysis.
# Instead of traditional OCR, we leverage the AI model's ability
# to understand images — much more powerful than Tesseract OCR.
#
# The model can read text in images, understand screenshots,
# and even interpret handwritten notes.

import base64

from config import settings
from openai import AsyncAzureOpenAI, AsyncOpenAI

# Reuse the same client configuration as classifier.py
if settings.use_azure:
    _client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_key,
        api_version="2024-12-01-preview",
    )
    _MODEL = settings.azure_openai_deployment
else:
    _client = AsyncOpenAI(api_key=settings.openai_api_key)
    _MODEL = settings.openai_model


# Map file extensions to MIME types for the Vision API
_IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


async def extract_text_from_image(filename: str, content: bytes) -> str:
    """
    Send an image to GPT Vision API and extract all visible text.

    How it works:
    1. Encode image to base64 (API requirement)
    2. Send as a "vision" message with instructions to extract text
    3. Return the extracted text

    .NET comparison: similar to calling Azure Cognitive Services OCR,
    but using GPT which understands context, not just characters.
    """
    # Determine MIME type from extension
    ext = filename[filename.rfind(".") :].lower()
    mime_type = _IMAGE_MIME_TYPES.get(ext, "image/jpeg")

    # Encode image to base64 for the API
    b64_image = base64.b64encode(content).decode("utf-8")

    response = await _client.chat.completions.create(
        model=_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Extract ALL visible text from this image exactly as written. "
                            "If the image contains customer feedback, a complaint, a review, "
                            "or any written text, return it verbatim. "
                            "If no text is visible, describe what you see in the image. "
                            "Return ONLY the extracted text, nothing else."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_image}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
        max_tokens=1000,
        temperature=0.1,
    )

    text = response.choices[0].message.content
    if not text or not text.strip():
        raise ValueError("Could not extract any text from the image")

    return text.strip()
