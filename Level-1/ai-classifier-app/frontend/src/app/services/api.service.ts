// api.service.ts  Backend Communication Service
// =================================================
// Same logic as HttpClient service in .NET.
// Sends requests to the FastAPI backend using Angular's HttpClient.
//
// This service returns RxJS Observables  a pattern you already know.
// In Week 2, we'll extend this for SSE streaming.

import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  ClassificationRequest,
  ClassificationResponse,
  FileClassificationResponse,
  HealthResponse,
} from '../models/classification.model';

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  // DI using inject() function in Angular 21
  private http = inject(HttpClient);

  // Backend address  in production this comes from environment files
  private baseUrl = 'http://localhost:8000/api';

  /**
   * Backend health check.
   * Verifies the API is up and running on first connection.
   */
  checkHealth(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.baseUrl}/health`);
  }

  /**
   * Classify customer feedback using AI.
   *
   * From Angular's perspective, very simple:
   * 1. Send HTTP POST
   * 2. Get result as Observable
   * 3. Subscribe in component or use async pipe
   *
   * What happens behind the scenes:
   * Angular -> FastAPI -> OpenAI -> FastAPI -> Angular
   */
  classifyFeedback(text: string): Observable<ClassificationResponse> {
    const request: ClassificationRequest = { text };
    return this.http.post<ClassificationResponse>(`${this.baseUrl}/classify`, request);
  }

  /**
   * Classify customer feedback from an uploaded file.
   *
   * Uses FormData to send the file as multipart/form-data.
   * Backend extracts text from the file, then classifies it.
   *
   * Supported formats: .pdf, .txt, .docx, .jpg, .jpeg, .png
   */
  classifyFile(file: File): Observable<FileClassificationResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<FileClassificationResponse>(`${this.baseUrl}/classify-file`, formData);
  }
}
