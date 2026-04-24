# classifier.py  AI Classification Service
# ============================================
# Business logic layer that communicates with the OpenAI API.
# Think of it as a Service class in .NET (IClassifierService).
#
# This is the most important file of this week.
# Teaches how to call OpenAI and the basics of "prompt engineering".

import asyncio
import json

from config import settings
from models import ClassificationResponse
from openai import AsyncAzureOpenAI, AsyncOpenAI
from prompt_manager import build_system_prompt, load_config

# -------------------------------------------------
# OpenAI Client Creation
# -------------------------------------------------
# Similar to HttpClientFactory in .NET  a single client instance,
# works efficiently with connection pooling.

if settings.use_azure:
    # Azure OpenAI usage (for corporate environments)
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_key,
        api_version="2024-12-01-preview",
        timeout=30.0,
    )
    MODEL = settings.azure_openai_deployment
else:
    # Direct OpenAI API usage
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
    MODEL = settings.openai_model


# -------------------------------------------------
# System Prompt  The Most Important Concept This Week
# -------------------------------------------------
# The system prompt tells the AI "who you are and how to behave".
# Good system prompt = good results. Bad prompt = bad results.
#
# The prompt is now dynamically built from editable variables
# stored in prompts/config.json. Users can modify these variables
# through the Prompt Settings UI tab without touching code.
#
# When writing prompts:
# 1. Define the role clearly ("You are a customer feedback analyst")
# 2. Specify the output format precisely (give a JSON schema)
# 3. List rules and constraints
# 4. Provide examples (few-shot learning)


async def classify_feedback(text: str) -> ClassificationResponse:
    """
    Classify customer feedback text using OpenAI.

    Step by step:
    1. Load prompt config and build system prompt dynamically
    2. Send system prompt + user text to OpenAI
    3. Receive JSON response
    4. Parse into Pydantic model (automatic validation)
    5. Return validated result

    .NET comparison:
    public async Task<ClassificationResponse> ClassifyFeedbackAsync(string text)
    {
        var response = await _httpClient.PostAsync("openai/...", content);
        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<ClassificationResponse>(json);
    }
    """

    # Load prompt config and build system prompt dynamically
    # -------------------------------------------------------
    # Each call reads the latest config so UI changes take effect immediately
    config = load_config()
    system_prompt = build_system_prompt(config)
    temperature = config.get("temperature", 0.1)

    # OpenAI API call
    # ----------------
    # model: Which model to use
    # messages: Chat history (system + user)
    # response_format: JSON mode  model strictly returns JSON
    # temperature: configurable via prompt settings UI
    #              (low temperature is ideal for classification)

    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        ),
        timeout=60.0,
    )

    # Parse the response
    # -------------------
    # response.choices[0].message.content -> raw JSON string from the model
    # json.loads() -> converts string to Python dict
    # ClassificationResponse(**result) -> converts dict to Pydantic model
    #   (if data is invalid, Pydantic automatically raises ValidationError)

    raw_json = response.choices[0].message.content
    result = json.loads(raw_json)

    return ClassificationResponse(**result)
