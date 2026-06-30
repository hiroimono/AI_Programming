import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';
import { SourceCitation, DocumentItem } from '../models/document.model';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: Date;
  sources?: SourceCitation[];
  /** Documents the user attached to *this specific* user message.
   *  Per-message (not per-conversation) so the chip stays anchored to
   *  the question it was attached to. */
  attachments?: DocumentItem[];
}

export type WritingMode = 'general' | 'blog' | 'email' | 'report' | 'creative';

/**
 * Stream events emitted by streamChat(). Discriminated union so the
 * caller can render tokens incrementally and attach citations once they
 * arrive (typically right before the [DONE] marker).
 */
export type StreamEvent =
  | { type: 'token'; content: string }
  | { type: 'sources'; sources: SourceCitation[] };

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private http = inject(HttpClient);
  private auth = inject(AuthService);
  private apiUrl = environment.gatewayUrl
    ? `${environment.gatewayUrl}/apps/writer/api`
    : environment.apiUrl;

  /**
   * Sends chat messages and streams responses as SSE.
   *
   * Emits a `token` event for each content chunk and (optionally) a
   * single `sources` event when RAG retrieval ran on the backend. Empty
   * sources array is also emitted on MISS so the UI can clear stale
   * citations from previous turns.
   */
  streamChat(
    messages: ChatMessage[],
    writingMode: WritingMode,
    conversationId?: string,
  ): Observable<StreamEvent> {
    return new Observable<StreamEvent>((subscriber) => {
      const abortController = new AbortController();

      const body: Record<string, unknown> = { messages, writing_mode: writingMode };
      if (conversationId) {
        body['conversation_id'] = conversationId;
      }

      fetch(`${this.apiUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(this.auth.getToken() ? { Authorization: `Bearer ${this.auth.getToken()}` } : {}),
        },
        body: JSON.stringify(body),
        signal: abortController.signal,
      })
        .then(async (response) => {
          if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Stream failed' }));
            subscriber.error(new Error(error.detail ?? `HTTP ${response.status}`));
            return;
          }

          const reader = response.body!.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          // Track the SSE event name across chunks. Resets on blank lines.
          let currentEvent: string | null = null;

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';

            for (const line of lines) {
              if (line === '') {
                // End of SSE message — reset the pending event name.
                currentEvent = null;
                continue;
              }
              if (line.startsWith('event: ')) {
                currentEvent = line.slice(7).trim();
                continue;
              }
              if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data === '[DONE]') {
                  subscriber.complete();
                  return;
                }
                try {
                  const parsed = JSON.parse(data);
                  if (currentEvent === 'sources' && Array.isArray(parsed)) {
                    subscriber.next({
                      type: 'sources',
                      sources: parsed as SourceCitation[],
                    });
                  } else if (parsed && typeof parsed.content === 'string') {
                    subscriber.next({ type: 'token', content: parsed.content });
                  }
                } catch {
                  // Skip malformed JSON
                }
              }
            }
          }

          subscriber.complete();
        })
        .catch((err) => {
          if (err.name !== 'AbortError') {
            subscriber.error(err);
          }
        });

      // Cleanup: abort fetch when unsubscribed
      return () => abortController.abort();
    });
  }
}
