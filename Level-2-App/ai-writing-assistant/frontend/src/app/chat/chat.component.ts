import { Component, inject, signal, ViewChild, ElementRef, OnInit, OnDestroy, NgZone, HostListener } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subscription } from 'rxjs';
import { ChatService, ChatMessage, WritingMode } from '../services/chat.service';

@Component({
  selector: 'app-chat',
  imports: [
    FormsModule,
    MatIconModule,
    MatTooltipModule,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent implements OnInit, OnDestroy {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;
  @ViewChild('chatTextarea') private chatTextarea!: ElementRef<HTMLTextAreaElement>;

  private chatService = inject(ChatService);
  private ngZone = inject(NgZone);
  private userScrolledUp = false;
  private wheelListener: ((e: WheelEvent) => void) | null = null;
  private streamSub: Subscription | null = null;

  messages = signal<ChatMessage[]>([]);
  userInput = '';
  isStreaming = signal(false);
  writingMode = signal<WritingMode>('general');
  copiedIndex = signal<number | null>(null);
  modeDropdownOpen = signal(false);

  writingModes: { value: WritingMode; label: string; icon: string }[] = [
    { value: 'general', label: 'General', icon: 'chat' },
    { value: 'blog', label: 'Blog Post', icon: 'article' },
    { value: 'email', label: 'Email', icon: 'email' },
    { value: 'report', label: 'Report', icon: 'description' },
    { value: 'creative', label: 'Creative', icon: 'auto_awesome' },
  ];

  ngOnInit() {
    setTimeout(() => this.attachScrollListener());
  }

  ngOnDestroy() {
    this.detachScrollListener();
    this.streamSub?.unsubscribe();
  }

  sendMessage() {
    const content = this.userInput.trim();
    if (!content || this.isStreaming()) return;

    const userMessage: ChatMessage = { role: 'user', content, timestamp: new Date() };
    this.messages.update((msgs) => [...msgs, userMessage]);
    this.userInput = '';
    this.resetTextarea();
    this.userScrolledUp = false;
    this.scheduleScroll();

    const assistantMessage: ChatMessage = { role: 'assistant', content: '', timestamp: new Date() };
    this.messages.update((msgs) => [...msgs, assistantMessage]);
    this.isStreaming.set(true);

    this.streamSub = this.chatService.streamChat(this.messages().slice(0, -1), this.writingMode()).subscribe({
      next: (token) => {
        this.messages.update((msgs) => {
          const updated = [...msgs];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, content: last.content + token };
          return updated;
        });
        this.scheduleScroll();
      },
      error: (err) => {
        this.messages.update((msgs) => {
          const updated = [...msgs];
          updated[updated.length - 1] = {
            role: 'assistant',
            content: `⚠️ Error: ${err.message}`,
            timestamp: new Date(),
          };
          return updated;
        });
        this.isStreaming.set(false);
      },
      complete: () => {
        this.isStreaming.set(false);
        this.messages.update((msgs) => {
          const updated = [...msgs];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, timestamp: new Date() };
          return updated;
        });
      },
    });
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  autoResize() {
    const textarea = this.chatTextarea?.nativeElement;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }

  clearChat() {
    this.messages.set([]);
  }

  cancelStream() {
    this.streamSub?.unsubscribe();
    this.streamSub = null;
    this.isStreaming.set(false);

    // Finalize the partial assistant message with a timestamp
    this.messages.update((msgs) => {
      const updated = [...msgs];
      const last = updated[updated.length - 1];
      if (last?.role === 'assistant') {
        updated[updated.length - 1] = { ...last, timestamp: new Date() };
      }
      return updated;
    });
  }

  toggleModeDropdown() {
    this.modeDropdownOpen.update((v) => !v);
  }

  selectMode(mode: WritingMode) {
    this.writingMode.set(mode);
    this.modeDropdownOpen.set(false);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    if (!this.modeDropdownOpen()) return;
    const target = event.target as HTMLElement;
    if (!target.closest('.mode-dropdown-wrapper')) {
      this.modeDropdownOpen.set(false);
    }
  }

  getActiveMode() {
    return this.writingModes.find((m) => m.value === this.writingMode())!;
  }

  copyMessage(index: number) {
    const msg = this.messages()[index];
    navigator.clipboard.writeText(msg.content);
    this.copiedIndex.set(index);
    setTimeout(() => this.copiedIndex.set(null), 2000);
  }

  formatTime(date?: Date): string {
    if (!date) return '';
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  }

  regenerateFrom(index: number) {
    if (this.isStreaming()) return;

    // Find the user message at or before this index
    const msgs = this.messages();
    let userMsgIndex = index;
    if (msgs[index].role === 'assistant' && index > 0) {
      userMsgIndex = index - 1;
    }

    // Keep messages up to and including the user message
    const kept = msgs.slice(0, userMsgIndex + 1);
    this.messages.set(kept);
    this.userScrolledUp = false;
    this.scheduleScroll();

    // Add empty assistant message and stream
    const assistantMessage: ChatMessage = { role: 'assistant', content: '', timestamp: new Date() };
    this.messages.update((m) => [...m, assistantMessage]);
    this.isStreaming.set(true);

    this.streamSub = this.chatService.streamChat(kept, this.writingMode()).subscribe({
      next: (token) => {
        this.messages.update((m) => {
          const updated = [...m];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, content: last.content + token };
          return updated;
        });
        this.scheduleScroll();
      },
      error: (err) => {
        this.messages.update((m) => {
          const updated = [...m];
          updated[updated.length - 1] = {
            role: 'assistant',
            content: `⚠️ Error: ${err.message}`,
            timestamp: new Date(),
          };
          return updated;
        });
        this.isStreaming.set(false);
      },
      complete: () => {
        this.isStreaming.set(false);
        this.messages.update((m) => {
          const updated = [...m];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, timestamp: new Date() };
          return updated;
        });
      },
    });
  }

  editMessage(index: number) {
    const msg = this.messages()[index];
    if (msg.role !== 'user') return;

    // Put the message content back in the input
    this.userInput = msg.content;
    this.autoResize();

    // Remove this message and everything after it
    this.messages.update((msgs) => msgs.slice(0, index));

    // Focus the textarea
    setTimeout(() => this.chatTextarea?.nativeElement?.focus());
  }

  private resetTextarea() {
    const textarea = this.chatTextarea?.nativeElement;
    if (textarea) {
      textarea.style.height = 'auto';
    }
  }

  private scrollToBottom() {
    const el = this.messagesContainer?.nativeElement;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }

  private scheduleScroll() {
    if (this.userScrolledUp) return;
    requestAnimationFrame(() => {
      if (!this.userScrolledUp) {
        this.scrollToBottom();
      }
    });
  }

  private isNearBottom(): boolean {
    const el = this.messagesContainer?.nativeElement;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < 100;
  }

  private attachScrollListener() {
    const el = this.messagesContainer?.nativeElement;
    if (!el) return;

    this.wheelListener = (e: WheelEvent) => {
      // Wheel up during streaming → pause auto-scroll instantly
      if (e.deltaY < 0 && this.isStreaming()) {
        this.userScrolledUp = true;
      }

      // Wheel down while paused → check if near bottom after browser applies scroll
      if (e.deltaY > 0 && this.userScrolledUp) {
        setTimeout(() => {
          if (this.isNearBottom()) {
            this.userScrolledUp = false;
          }
        }, 60);
      }
    };

    el.addEventListener('wheel', this.wheelListener, { passive: true });
  }

  private detachScrollListener() {
    const el = this.messagesContainer?.nativeElement;
    if (!el) return;
    if (this.wheelListener) {
      el.removeEventListener('wheel', this.wheelListener);
    }
  }
}
