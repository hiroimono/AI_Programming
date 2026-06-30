import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  DocumentChunksResponse,
  DocumentItem,
  DocumentUploadResponse,
} from '../models/document.model';

interface DocumentListResponse {
  documents: DocumentItem[];
}

@Injectable({
  providedIn: 'root',
})
export class DocumentService {
  private http = inject(HttpClient);
  private apiUrl = environment.gatewayUrl
    ? `${environment.gatewayUrl}/apps/writer/api`
    : environment.apiUrl;

  /**
   * Upload a document scoped to a conversation. The Gateway proxies the
   * multipart request to the Writer backend, which forwards it to
   * rag-service. Auth header is added by the global auth interceptor.
   */
  upload(conversationId: string, file: File): Observable<DocumentUploadResponse> {
    const form = new FormData();
    form.append('file', file);
    form.append('conversation_id', conversationId);
    return this.http.post<DocumentUploadResponse>(`${this.apiUrl}/documents`, form);
  }

  /**
   * List documents for the current user, optionally filtered by conversation.
   * Returns the inner array (DocumentItem[]) for easier consumption.
   */
  list(conversationId?: string): Observable<DocumentItem[]> {
    let params = new HttpParams();
    if (conversationId) {
      params = params.set('conversation_id', conversationId);
    }
    return new Observable<DocumentItem[]>((subscriber) => {
      const sub = this.http
        .get<DocumentListResponse>(`${this.apiUrl}/documents`, { params })
        .subscribe({
          next: (res) => subscriber.next(res.documents ?? []),
          error: (err) => subscriber.error(err),
          complete: () => subscriber.complete(),
        });
      return () => sub.unsubscribe();
    });
  }

  delete(documentId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/documents/${documentId}`);
  }

  /**
   * Fetch the chunked parsed-text view of a document for the preview modal.
   * Chunks come back in ascending chunk_index order so the FE can render
   * or concatenate them as-is.
   */
  getChunks(documentId: string): Observable<DocumentChunksResponse> {
    return this.http.get<DocumentChunksResponse>(
      `${this.apiUrl}/documents/${documentId}/chunks`,
    );
  }

  /**
   * Stream the original uploaded file as a Blob. Component is responsible
   * for creating + revoking the object URL. Uses observe:'response' so we
   * can inspect content-type (browser preview decisions depend on it).
   */
  getFileBlob(documentId: string): Observable<{ blob: Blob; contentType: string }> {
    return new Observable((subscriber) => {
      const sub = this.http
        .get(`${this.apiUrl}/documents/${documentId}/file`, {
          responseType: 'blob',
          observe: 'response',
        })
        .subscribe({
          next: (res) => {
            const contentType =
              res.headers.get('content-type') ?? res.body?.type ?? 'application/octet-stream';
            subscriber.next({ blob: res.body!, contentType });
          },
          error: (err) => subscriber.error(err),
          complete: () => subscriber.complete(),
        });
      return () => sub.unsubscribe();
    });
  }
}
