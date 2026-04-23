// classification.model.ts  Data Models
// =======================================
// TypeScript equivalent of backend Pydantic models.
// Think of it as a shared DTO project in .NET  frontend and backend
// speak the same data structure.

/** Request sent from Angular to the backend */
export interface ClassificationRequest {
  text: string;
}

/** Response returned from the backend to Angular */
export interface ClassificationResponse {
  category: 'Complaint' | 'Suggestion' | 'Question' | 'Praise';
  sentiment: 'Positive' | 'Negative' | 'Neutral';
  confidence: number;
  summary: string;
  suggestions: string[];
}

/** Health check response */
export interface HealthResponse {
  status: string;
  model: string;
}

/** Response for file-based classification */
export interface FileClassificationResponse {
  filename: string;
  extracted_text: string;
  classification: ClassificationResponse;
}
