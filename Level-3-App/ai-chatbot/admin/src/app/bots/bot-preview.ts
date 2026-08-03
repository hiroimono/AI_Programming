import {
  AfterViewChecked,
  Component,
  ElementRef,
  Input,
  OnInit,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { environment } from '../../environments/environment';
import { ChatMessage, ChatSource, WidgetConfig } from '../models/preview.model';
import { parseSSE } from '../shared/sse';
import { BotService } from '../services/bot.service';
import { ToastService } from '../services/toast.service';

/**
 * Preview tab: an in-panel chat that talks to the bot exactly like the public
 * widget does, but authenticated with a short-lived PREVIEW token minted via
 * POST /api/bots/:id/preview-session. Streaming + event handling mirror the
 * widget (meta/sources/delta/done/error events).
 */
@Component({
  selector: 'app-bot-preview',
  imports: [FormsModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  templateUrl: './bot-preview.html',
  styleUrl: './bot-preview.scss',
})
export class BotPreviewComponent implements OnInit, AfterViewChecked {
  @Input({ required: true }) botId!: string;
  @ViewChild('scrollEl') private scrollEl?: ElementRef<HTMLElement>;

  private botService = inject(BotService);
  private toast = inject(ToastService);

  readonly loadingSession = signal(true);
  readonly sessionError = signal(false);
  readonly config = signal<WidgetConfig | null>(null);
  readonly messages = signal<ChatMessage[]>([]);
  readonly sending = signal(false);
  draft = '';

  private token: string | null = null;
  private conversationId: string | null = null;
  private shouldScroll = false;

  ngOnInit(): void {
    this.openSession();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll && this.scrollEl) {
      this.scrollEl.nativeElement.scrollTop = this.scrollEl.nativeElement.scrollHeight;
      this.shouldScroll = false;
    }
  }

  /** True once at least one user turn exists (suggested chips then hide). */
  hasUserMessages(): boolean {
    return this.messages().some((m) => m.role === 'user');
  }

  /** Unique source file names under an assistant answer. */
  uniqueSources(message: ChatMessage): string[] {
    const names = (message.sources ?? []).map((s: ChatSource) => s.file_name);
    return [...new Set(names)];
  }

  reset(): void {
    this.conversationId = null;
    this.token = null;
    this.messages.set([]);
    this.openSession();
  }

  ask(question: string): void {
    this.draft = question;
    this.send();
  }

  send(): void {
    const text = this.draft.trim();
    if (!text || this.sending() || !this.token) {
      return;
    }
    this.draft = '';
    const userMsg: ChatMessage = { role: 'user', content: text };
    const assistant: ChatMessage = { role: 'assistant', content: '', streaming: true };
    this.messages.update((m) => [...m, userMsg, assistant]);
    this.sending.set(true);
    this.touchScroll();
    void this.stream(text, assistant);
  }

  private openSession(): void {
    this.loadingSession.set(true);
    this.sessionError.set(false);
    this.botService.openPreviewSession(this.botId).subscribe({
      next: (res) => {
        this.token = res.access_token;
        this.config.set(res.config);
        this.loadingSession.set(false);
        this.messages.set([{ role: 'assistant', content: res.config.welcome_message }]);
        this.touchScroll();
      },
      error: () => {
        this.loadingSession.set(false);
        this.sessionError.set(true);
      },
    });
  }

  private async stream(text: string, assistant: ChatMessage): Promise<void> {
    try {
      const resp = await fetch(`${environment.apiBase}/api/widget/chat`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text,
          conversation_id: this.conversationId ?? undefined,
        }),
      });
      if (!resp.ok || !resp.body) {
        throw new Error(`chat failed (${resp.status})`);
      }
      for await (const ev of parseSSE(resp)) {
        this.applyEvent(ev.event, ev.data, assistant);
      }
    } catch {
      if (!assistant.content) {
        assistant.content = 'Something went wrong. The preview session may have expired.';
      }
      this.toast.error('Preview chat failed. Try "New session".');
    } finally {
      assistant.streaming = false;
      this.sending.set(false);
      this.messages.update((m) => [...m]);
      this.touchScroll();
    }
  }

  private applyEvent(event: string, data: unknown, assistant: ChatMessage): void {
    const payload = (data ?? {}) as Record<string, unknown>;
    switch (event) {
      case 'meta':
        this.conversationId = String(payload['conversation_id'] ?? '') || null;
        break;
      case 'sources':
        assistant.sources = Array.isArray(data) ? (data as ChatSource[]) : [];
        break;
      case 'delta':
        assistant.content += String(payload['text'] ?? '');
        break;
      case 'done':
        assistant.streaming = false;
        break;
      case 'error':
        if (!assistant.content) {
          assistant.content = String(payload['message'] ?? 'Something went wrong.');
        }
        assistant.streaming = false;
        break;
      default:
        break;
    }
    this.messages.update((m) => [...m]);
    this.touchScroll();
  }

  private touchScroll(): void {
    this.shouldScroll = true;
  }
}
