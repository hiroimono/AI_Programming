import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export type WritingMode = 'general' | 'blog' | 'email' | 'report' | 'creative';

@Injectable({
  providedIn: 'root',
})
export class ChatService {
  private http = inject(HttpClient);
  private apiUrl = environment.gatewayUrl
    ? `${environment.gatewayUrl}/apps/writer/api`
    : environment.apiUrl;

  /**
   * Sends chat messages to backend and returns an Observable that emits
   * streamed tokens via SSE (Server-Sent Events).
   *
   * RxJS concept: We create a custom Observable that reads from an SSE stream.
   * Unlike a normal HTTP call that returns one response, this keeps emitting
   * values until the stream closes — similar to a WebSocket but one-directional.
   */
  streamChat(messages: ChatMessage[], writingMode: WritingMode): Observable<string> {
    return new Observable<string>((subscriber) => {
      const abortController = new AbortController();

      fetch(`${this.apiUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, writing_mode: writingMode }),
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

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data === '[DONE]') {
                  subscriber.complete();
                  return;
                }
                try {
                  const parsed = JSON.parse(data);
                  if (parsed.content) {
                    subscriber.next(parsed.content);
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
