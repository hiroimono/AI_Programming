# Week 1: Python & FastAPI Fundamentals + First AI Call

## 🎯 What Are We Building This Week?

**App:** Smart Customer Feedback Classifier

A text box. You type in customer feedback. Click "Analyze".
AI automatically:

- Determines the **Category** (Complaint, Suggestion, Question, Praise)
- Performs **Sentiment analysis** (Positive, Negative, Neutral)
- Gives a **Confidence score** (0-100%)
- Produces a **Summary**
- Offers **Action suggestions**

This solves a real business problem: instead of a customer service team
manually reading hundreds of feedback items per day, they get automatic classification.

---

## 📐 Architecture (This Week)

```text
┌─────────────────┐     HTTP POST      ┌─────────────────┐     API Call     ┌──────────┐
│   Angular App   │ ──────────────────► │   FastAPI       │ ───────────────► │  OpenAI  │
│   (localhost:    │ ◄────────────────── │   Backend       │ ◄─────────────── │  GPT-4o  │
│    4200)         │     JSON Response   │   (localhost:   │    JSON Response │  mini    │
│                  │                     │    8000)        │                  │          │
└─────────────────┘                     └─────────────────┘                  └──────────┘
```

Very simple: Angular → FastAPI → OpenAI → return. That's it.

---

## 🔧 Daily Plan

### Days 1-2: Python Setup + Fundamentals (~2 hours)

**How different is Python from .NET/C#?**

Short answer: Not much. Just syntax differences. Logic is the same.

| C# / .NET                      | Python                         |
| ------------------------------ | ------------------------------ |
| `string name = "Ali";`         | `name = "Ali"`                 |
| `int age = 30;`                | `age = 30`                     |
| `List<string> items = new();`  | `items = []`                   |
| `Dictionary<string, int>`      | `dict` → `{"key": value}`      |
| `public class User { ... }`    | `class User: ...`              |
| `async Task<string> GetData()` | `async def get_data() -> str:` |
| `namespace MyApp { ... }`      | File = module (no namespace)   |
| `using System.Net.Http;`       | `import httpx`                 |
| NuGet packages                 | pip packages                   |
| `appsettings.json`             | `.env` file                    |
| `[ApiController]` attribute    | `@app.post("/path")` decorator |

**Setup steps are in WEEK-1-SETUP.md.**

### Days 3-4: Building the FastAPI Backend (~2 hours)

FastAPI is very similar to .NET Minimal API:

```text
// .NET Minimal API              # FastAPI (Python)
app.MapPost("/classify",         @app.post("/classify")
  async (Request req) =>         async def classify(req: Request):
  {                                  result = await process(req)
    var result = await             return result
      Process(req);
    return result;
  });
```

In this phase, we'll write the backend code and make the first call to OpenAI.

### Days 5-6: Angular Frontend + Integration (~2 hours)

You already know Angular. Just:

1. Create project with `ng new`
2. Write a form component
3. POST with HttpClient
4. Display results nicely

### Day 7: Testing + Experiments (~1 hour)

Test with different texts. Modify the prompt. Observe the results.
First steps of "Prompt Engineering".

---

## 📁 Project Structure

```text
ai-classifier-app/
├── backend/
│   ├── main.py              ← FastAPI application entry point
│   ├── models.py            ← Pydantic models (Python equivalent of DTOs)
│   ├── classifier.py        ← OpenAI API call and business logic
│   ├── config.py            ← Configuration management
│   ├── requirements.txt     ← Python equivalent of NuGet packages
│   └── .env.example         ← API key template
│
└── frontend/                ← Angular application (created with ng new)
    └── src/
        └── app/
            ├── classifier/
            │   ├── classifier.component.ts
            │   ├── classifier.component.html
            │   └── classifier.component.css
            ├── services/
            │   └── api.service.ts
            └── models/
                └── classification.model.ts
```

---

## 🧠 Core Concepts

### How Does the OpenAI API Work?

OpenAI's API is a REST service. You send it:

1. A **system prompt** (defines the role and rules)
2. A **user message** (the text written by the user)

It returns a JSON response.

```json
POST https://api.openai.com/v1/chat/completions
{
  "model": "gpt-4o-mini",          ← Which model to use
  "temperature": 0.1,               ← How "creative" (0=strict, 1=creative)
  "response_format": {"type": "json_object"},  ← Return JSON
  "messages": [
    {"role": "system", "content": "You are a classifier..."},
    {"role": "user", "content": "Your product is terrible, I want a refund!"}
  ]
}
```

**gpt-4o-mini** model:

- Very cheap (~$0.15 / 1M input tokens)
- Fast
- More than sufficient for classification tasks
- 1000 classifications cost ~$0.02

### Pydantic = DTOs + DataAnnotations in C#

```python
# In C#:                               # In Python (Pydantic):
# public class Request                  class Request(BaseModel):
# {                                         text: str = Field(
#   [Required]                                  ...,
#   [MaxLength(2000)]                           min_length=10,
#   public string Text { get; set; }            max_length=2000
# }                                         )
```

Pydantic automatically validates incoming data. If invalid data comes in,
it returns a 422 error. Like ModelState.IsValid in .NET, but automatic.

---

## ⚠️ Getting an OpenAI API Key

1. Go to https://platform.openai.com/signup
2. Create an account (you can sign in with Google)
3. https://platform.openai.com/api-keys → "Create new secret key"
4. Copy the key (starts with sk-...)
5. **IMPORTANT:** You'll need to load $5 credit (Settings → Billing)
   - gpt-4o-mini is very cheap, $5 lasts for weeks
   - The entire training costs ~$2-3 in API costs

> 💡 If there are restrictions on the company computer, Azure OpenAI can also be used.
> The code is written to support both services.

---

## 🚀 Ready?

Follow this order:

1. **WEEK-1-SETUP.md** → Install Python and dependencies
2. Examine and run the code in the **backend/** folder
3. Create the Angular app in **frontend/** and connect it
4. Test and experiment by modifying the prompt

Every file has English comments and .NET/C# comparisons.
