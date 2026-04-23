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

/** Response for multi-file batch classification */
export interface BatchClassificationResponse {
  results: FileClassificationResponse[];
  errors: string[];
  summary: Record<string, number>;
}

/** SSE progress event from batch classification */
export interface BatchProgressEvent {
  index: number;
  total: number;
  filename: string;
  result?: FileClassificationResponse;
  error?: string;
}

/** Category stats from output folder */
export type CategoryStats = Record<string, number>;

/** File entry from the output folder */
export interface OutputFile {
  filename: string;
  category: string;
  size: number;
}
