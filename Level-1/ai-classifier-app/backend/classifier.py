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
# When writing prompts:
# 1. Define the role clearly ("You are a customer feedback analyst")
# 2. Specify the output format precisely (give a JSON schema)
# 3. List rules and constraints
# 4. Provide examples (few-shot learning)

SYSTEM_PROMPT = """You are a corporate customer feedback analysis expert.

Your task: Analyze the given customer feedback text and classify it in JSON format.
Give your answers always in Turkish.

## Output Format (return strictly in this JSON structure):
{
  "category": "Complaint | Suggestion | Question | Praise",
  "sentiment": "Positive | Negative | Neutral",
  "confidence": a number between 0.0 and 1.0,
  "summary": "1-2 sentence summary of the feedback",
  "suggestions": ["Suggested action 1", "Suggested action 2"]
}

## Rules:
1. category MUST be one of these 4 values: Complaint, Suggestion, Question, Praise
2. sentiment MUST be one of these 3 values: Positive, Negative, Neutral
3. confidence: CRITICAL — you MUST calibrate confidence strictly based on text clarity:
   - 0.9-1.0: Text is 100% clear, only ONE category applies, no ambiguity at all
   - 0.7-0.89: Text mostly fits one category but contains a minor secondary signal
   - 0.5-0.69: Text mixes TWO categories (e.g. complaint + suggestion)
   - 0.3-0.49: Text contains contradictions, sarcasm, or signals from 3+ categories
   - below 0.3: Text is incoherent, self-contradictory, or deliberately confusing
   IMPORTANT: If the text contains sarcasm, irony, contradictory statements, or
   mixes praise with complaints in the same sentence, confidence MUST be below 0.5.
   Never give high confidence to ambiguous or mixed-signal texts.
4. summary: should be concise and in the same language as the input text.
   If the text is contradictory or sarcastic, explicitly mention that in the summary.
5. suggestions: minimum 1, maximum 3 action suggestions. Must be practical and actionable.
6. Your response MUST be ONLY JSON, do not write anything else.

## Examples of low-confidence texts (confidence should be 0.2-0.4):
- "Ürün harika ama çöpe attım" (contradictory: praise + negative action)
- "Teşekkür ederim bozuk geldiği için" (sarcasm: gratitude + complaint)
- "Çok memnunum, bir daha almam" (contradictory: satisfaction + rejection)
- Mixed feedback touching complaint, praise, and question in the same text"""


async def classify_feedback(text: str) -> ClassificationResponse:
    """
    Classify customer feedback text using OpenAI.

    Step by step:
    1. Send system prompt + user text to OpenAI
    2. Receive JSON response
    3. Parse into Pydantic model (automatic validation)
    4. Return validated result

    .NET comparison:
    public async Task<ClassificationResponse> ClassifyFeedbackAsync(string text)
    {
        var response = await _httpClient.PostAsync("openai/...", content);
        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<ClassificationResponse>(json);
    }
    """

    # OpenAI API call
    # ----------------
    # model: Which model to use
    # messages: Chat history (system + user)
    # response_format: JSON mode  model strictly returns JSON
    # temperature: 0.1 = very consistent/deterministic results
    #              (low temperature is ideal for classification)

    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
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
