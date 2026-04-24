# prompt_manager.py  System Prompt Management
# ============================================
# Manages prompt configuration as editable variables.
# Stores prompt config in a JSON file so changes persist across restarts.
#
# .NET comparison: IOptionsSnapshot<PromptConfig> with JSON config file

import json
import os
from copy import deepcopy
from typing import Any

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
CONFIG_FILE = os.path.join(PROMPTS_DIR, "config.json")

# -------------------------------------------------
# Default Prompt Configuration
# -------------------------------------------------
DEFAULT_CONFIG: dict[str, Any] = {
    "role": "You are a corporate customer feedback analysis expert.",
    "task": "Analyze the given customer feedback text and classify it in JSON format.",
    "response_language": "Turkish",
    "categories": ["Complaint", "Suggestion", "Question", "Praise"],
    "sentiments": ["Positive", "Negative", "Neutral"],
    "confidence_calibration": [
        {
            "range": "0.9-1.0",
            "description": "Text is 100% clear, only ONE category applies, no ambiguity at all",
        },
        {
            "range": "0.7-0.89",
            "description": "Text mostly fits one category but contains a minor secondary signal",
        },
        {
            "range": "0.5-0.69",
            "description": "Text mixes TWO categories (e.g. complaint + suggestion)",
        },
        {
            "range": "0.3-0.49",
            "description": "Text contains contradictions, sarcasm, or signals from 3+ categories",
        },
        {
            "range": "below 0.3",
            "description": "Text is incoherent, self-contradictory, or deliberately confusing",
        },
    ],
    "low_confidence_warning": (
        "If the text contains sarcasm, irony, contradictory statements, or "
        "mixes praise with complaints in the same sentence, confidence MUST be below 0.5. "
        "Never give high confidence to ambiguous or mixed-signal texts."
    ),
    "low_confidence_examples": [
        '"Ürün harika ama çöpe attım" (contradictory: praise + negative action)',
        '"Teşekkür ederim bozuk geldiği için" (sarcasm: gratitude + complaint)',
        '"Çok memnunum, bir daha almam" (contradictory: satisfaction + rejection)',
        "Mixed feedback touching complaint, praise, and question in the same text",
    ],
    "summary_instruction": "Should be concise and in the same language as the input text. If the text is contradictory or sarcastic, explicitly mention that in the summary.",
    "max_suggestions": 3,
    "additional_rules": "",
    "temperature": 0.1,
}


def _ensure_dir() -> None:
    """Create prompts directory if it doesn't exist."""
    os.makedirs(PROMPTS_DIR, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load prompt config from JSON file, or return defaults if not found."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # Merge with defaults so new keys are always present
        merged = deepcopy(DEFAULT_CONFIG)
        merged.update(saved)
        return merged
    return deepcopy(DEFAULT_CONFIG)


def save_config(config: dict[str, Any]) -> None:
    """Save prompt config to JSON file."""
    _ensure_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def reset_config() -> dict[str, Any]:
    """Reset to default config and save."""
    _ensure_dir()
    config = deepcopy(DEFAULT_CONFIG)
    save_config(config)
    return config


def get_default_config() -> dict[str, Any]:
    """Return a copy of the default config (for comparison)."""
    return deepcopy(DEFAULT_CONFIG)


def build_system_prompt(config: dict[str, Any] | None = None) -> str:
    """
    Build the full system prompt string from config variables.
    This is the template engine that assembles the final prompt.
    """
    if config is None:
        config = load_config()

    categories_str = " | ".join(config["categories"])
    sentiments_str = " | ".join(config["sentiments"])

    # Build confidence calibration section
    calibration_lines = []
    for item in config["confidence_calibration"]:
        calibration_lines.append(f'   - {item["range"]}: {item["description"]}')
    calibration_block = "\n".join(calibration_lines)

    # Build low-confidence examples
    examples_lines = []
    for ex in config["low_confidence_examples"]:
        examples_lines.append(f"- {ex}")
    examples_block = "\n".join(examples_lines)

    # Build additional rules
    additional = ""
    if config.get("additional_rules", "").strip():
        additional = f"\n7. Additional rules: {config['additional_rules']}"

    prompt = f"""{config["role"]}

Your task: {config["task"]}
Give your answers always in {config["response_language"]}.

## Output Format (return strictly in this JSON structure):
{{
  "category": "{categories_str}",
  "sentiment": "{sentiments_str}",
  "confidence": a number between 0.0 and 1.0,
  "summary": "1-2 sentence summary of the feedback",
  "suggestions": ["Suggested action 1", "Suggested action 2"]
}}

## Rules:
1. category MUST be one of these {len(config["categories"])} values: {categories_str}
2. sentiment MUST be one of these {len(config["sentiments"])} values: {sentiments_str}
3. confidence: CRITICAL — you MUST calibrate confidence strictly based on text clarity:
{calibration_block}
   IMPORTANT: {config["low_confidence_warning"]}
4. summary: {config["summary_instruction"]}
5. suggestions: minimum 1, maximum {config["max_suggestions"]} action suggestions. Must be practical and actionable.
6. Your response MUST be ONLY JSON, do not write anything else.{additional}

## Examples of low-confidence texts (confidence should be 0.2-0.4):
{examples_block}"""

    return prompt
