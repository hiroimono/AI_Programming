import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { DocumentItem } from '../models/document.model';

/**
 * Document (RAG knowledge base) API client, scoped to a bot.
 *
 * Upload is multipart/form-data — we intentionally do NOT set a Content-Type
 * header so the browser adds the correct multipart boundary automatically.
 */
@Injectable({ providedIn: 'root' })
export class DocumentService {
  private http = inject(HttpClient);
  private apiBase = environment.apiBase;

  private docsBase(botId: string): string {
    return `${this.apiBase}/api/bots/${botId}/documents`;
  }

  list(botId: string): Observable<DocumentItem[]> {
    return this.http.get<DocumentItem[]>(this.docsBase(botId));
  }

  upload(botId: string, file: File): Observable<DocumentItem> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post<DocumentItem>(this.docsBase(botId), form);
  }

  remove(botId: string, documentId: string): Observable<void> {
    return this.http.delete<void>(`${this.docsBase(botId)}/${documentId}`);
  }
}
