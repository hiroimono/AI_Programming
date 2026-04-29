# models.py  Pydantic Models (DTOs)
# ====================================
# Equivalent of DTO (Data Transfer Object) + DataAnnotations in .NET.
# Pydantic automatically validates and converts incoming/outgoing data.
#
# .NET comparison:
#   public class ClassificationRequest
#   {
#       [Required]
#       [StringLength(2000, MinimumLength = 10)]
#       public string Text { get; set; }
#   }

from pydantic import BaseModel, Field


class ClassificationRequest(BaseModel):
    """
    Request coming from Angular.
    Field() = equivalent of [Required], [MaxLength] attributes in .NET.
    """

    text: str = Field(
        ...,  # ... = Required (mandatory field)
        min_length=10,
        max_length=2000,
        description="Customer feedback text to classify",
        examples=["Your product is amazing, I'm very satisfied!"],
    )


class ClassificationResponse(BaseModel):
    """
    Response sent back to Angular.
    OpenAI's JSON output will be parsed into this model.
    """

    category: str = Field(
        ...,
        description="Feedback category: Complaint, Suggestion, Question, Praise",
    )
    sentiment: str = Field(
        ...,
        description="Sentiment analysis: Positive, Negative, Neutral",
    )
    confidence: float = Field(
        ...,
        ge=0.0,  # >= 0
        le=1.0,  # <= 1
        description="Confidence score (0.0 - 1.0)",
    )
    summary: str = Field(
        ...,
        description="Brief summary of the feedback",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="List of suggested actions",
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model: str


class FileClassificationResponse(BaseModel):
    """
    Response for file-based classification.
    Extends the text classification with file metadata.
    """

    filename: str = Field(..., description="Original uploaded filename")
    extracted_text: str = Field(..., description="Text extracted from the file")
    classification: ClassificationResponse = Field(
        ..., description="AI classification result"
    )
