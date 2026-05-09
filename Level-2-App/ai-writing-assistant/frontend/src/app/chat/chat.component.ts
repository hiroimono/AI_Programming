import { Component, inject, signal, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ChatService, ChatMessage, WritingMode } from '../services/chat.service';

@Component({
  selector: 'app-chat',
  imports: [
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatSelectModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent implements AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  private chatService = inject(ChatService);
  private shouldScroll = false;

  messages = signal<ChatMessage[]>([]);
  userInput = '';
  isStreaming = signal(false);
  writingMode = signal<WritingMode>('general');

  writingModes: { value: WritingMode; label: string; icon: string }[] = [
    { value: 'general', label: 'General', icon: 'chat' },
    { value: 'blog', label: 'Blog Post', icon: 'article' },
    { value: 'email', label: 'Email', icon: 'email' },
    { value: 'report', label: 'Report', icon: 'description' },
    { value: 'creative', label: 'Creative', icon: 'auto_awesome' },
  ];

  ngAfterViewChecked() {
    if (this.shouldScroll) {
      this.scrollToBottom();
      this.shouldScroll = false;
    }
  }

  sendMessage() {
    const content = this.userInput.trim();
    if (!content || this.isStreaming()) return;

    // Add user message
    const userMessage: ChatMessage = { role: 'user', content };
    this.messages.update((msgs) => [...msgs, userMessage]);
    this.userInput = '';
    this.shouldScroll = true;

    // Add empty assistant message (will be filled by stream)
    const assistantMessage: ChatMessage = { role: 'assistant', content: '' };
    this.messages.update((msgs) => [...msgs, assistantMessage]);
    this.isStreaming.set(true);

    // Stream the response
    this.chatService.streamChat(this.messages().slice(0, -1), this.writingMode()).subscribe({
      next: (token) => {
        this.messages.update((msgs) => {
          const updated = [...msgs];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, content: last.content + token };
          return updated;
        });
        this.shouldScroll = true;
      },
      error: (err) => {
        this.messages.update((msgs) => {
          const updated = [...msgs];
          updated[updated.length - 1] = {
            role: 'assistant',
            content: `⚠️ Error: ${err.message}`,
          };
          return updated;
        });
        this.isStreaming.set(false);
      },
      complete: () => {
        this.isStreaming.set(false);
      },
    });
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  clearChat() {
    this.messages.set([]);
  }

  private scrollToBottom() {
    const el = this.messagesContainer?.nativeElement;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }
}
