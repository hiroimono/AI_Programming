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
  BatchClassificationResponse,
  BatchProgressEvent,
  CategoryStats,
  ClassificationRequest,
  ClassificationResponse,
  FileClassificationResponse,
  HealthResponse,
  OutputFile,
  PromptConfig,
  PromptConfigResponse,
} from '../models/classification.model';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  // DI using inject() function in Angular 21
  private http = inject(HttpClient);

  // API URL from environment config (localhost for dev, Railway URL for prod)
  private baseUrl = environment.apiUrl;

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

  /**
   * Classify multiple files via SSE stream for real-time progress.
   * Each file completion fires an onProgress callback.
   * Returns a promise resolving with the final BatchClassificationResponse.
   */
  classifyFilesStream(
    files: File[],
    onProgress: (event: BatchProgressEvent) => void,
  ): { promise: Promise<BatchClassificationResponse>; abort: () => void } {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }

    const abortController = new AbortController();

    const promise = new Promise<BatchClassificationResponse>((resolve, reject) => {
      fetch(`${this.baseUrl}/classify-files`, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
      })
        .then((response) => {
          if (!response.ok) {
            return response.json().then((err) => {
              reject(new Error(err.detail || 'Server error'));
            });
          }

          const reader = response.body!.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          const processStream = (): Promise<void> => {
            return reader.read().then(({ done, value }) => {
              if (done) {
                reject(new Error('Stream ended without complete event'));
                return;
              }

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop() || '';

              let eventType = '';
              for (const line of lines) {
                if (line.startsWith('event: ')) {
                  eventType = line.substring(7).trim();
                } else if (line.startsWith('data: ')) {
                  const data = JSON.parse(line.substring(6));
                  if (eventType === 'progress') {
                    onProgress(data as BatchProgressEvent);
                  } else if (eventType === 'complete') {
                    resolve(data as BatchClassificationResponse);
                    return;
                  }
                }
              }

              return processStream();
            });
          };

          return processStream();
        })
        .catch((err) => {
          if (err.name !== 'AbortError') {
            reject(err);
          }
        });
    });

    return { promise, abort: () => abortController.abort() };
  }

  /**
   * Download organized classification results as a ZIP file.
   * The ZIP contains category folders with the original files + results.json.
   */
  downloadResults(): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/download-results`, {
      responseType: 'blob',
    });
  }

  /** Classify text AND save it as a .txt file in output/{Category}/ */
  classifyAndSave(
    text: string,
  ): Observable<{ classification: ClassificationResponse; saved_filename: string }> {
    const request: ClassificationRequest = { text };
    return this.http.post<{ classification: ClassificationResponse; saved_filename: string }>(
      `${this.baseUrl}/classify-text`,
      request,
    );
  }

  /** Get file count per category from output folder */
  getCategoryStats(): Observable<CategoryStats> {
    return this.http.get<CategoryStats>(`${this.baseUrl}/category-stats`);
  }

  /** List all classified files in output folder */
  getFiles(): Observable<OutputFile[]> {
    return this.http.get<OutputFile[]>(`${this.baseUrl}/files`);
  }

  /** Delete a file from a category folder */
  deleteFile(category: string, filename: string): Observable<unknown> {
    return this.http.delete(`${this.baseUrl}/files/${category}/${filename}`);
  }

  /** Bulk delete multiple files */
  bulkDeleteFiles(
    items: { category: string; filename: string }[],
  ): Observable<{ deleted: string[]; failed: string[] }> {
    return this.http.post<{ deleted: string[]; failed: string[] }>(
      `${this.baseUrl}/files/bulk-delete`,
      items,
    );
  }

  /** Move a file from one category to another */
  moveFile(filename: string, fromCategory: string, toCategory: string): Observable<unknown> {
    return this.http.post(`${this.baseUrl}/files/move`, null, {
      params: {
        filename,
        from_category: fromCategory,
        to_category: toCategory,
      },
    });
  }

  /** Get text preview of a file */
  previewFile(
    category: string,
    filename: string,
  ): Observable<{ filename: string; category: string; size: number; text: string }> {
    return this.http.get<{ filename: string; category: string; size: number; text: string }>(
      `${this.baseUrl}/files/${category}/${encodeURIComponent(filename)}/preview`,
    );
  }

  /** Generate random test files as a downloadable ZIP */
  generateTestFiles(count: number = 40): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/generate-test-files`, null, {
      params: { count: count.toString() },
      responseType: 'blob',
    });
  }

  /**
   * Watch the output directory for real-time file system changes via SSE.
   * Returns an EventSource that emits 'change' events when files
   * are added, modified, or deleted (even manually via Windows Explorer).
   * Caller is responsible for closing the EventSource when done.
   */
  watchFileChanges(onChange: () => void): EventSource {
    const es = new EventSource(`${this.baseUrl}/files/watch`);
    es.addEventListener('change', () => onChange());
    return es;
  }

  /** Get current prompt configuration */
  getPromptConfig(): Observable<PromptConfigResponse> {
    return this.http.get<PromptConfigResponse>(`${this.baseUrl}/prompt-config`);
  }

  /** Update prompt configuration */
  updatePromptConfig(config: PromptConfig): Observable<PromptConfigResponse> {
    return this.http.put<PromptConfigResponse>(`${this.baseUrl}/prompt-config`, config);
  }

  /** Reset prompt configuration to defaults */
  resetPromptConfig(): Observable<PromptConfigResponse> {
    return this.http.post<PromptConfigResponse>(`${this.baseUrl}/prompt-config/reset`, null);
  }

  /** Get default prompt configuration for comparison */
  getDefaultPromptConfig(): Observable<PromptConfigResponse> {
    return this.http.get<PromptConfigResponse>(`${this.baseUrl}/prompt-config/default`);
  }
}
