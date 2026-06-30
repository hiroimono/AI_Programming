import {
  Component,
  inject,
  signal,
  ViewChild,
  ElementRef,
  OnInit,
  OnDestroy,
  NgZone,
  HostListener,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subscription } from 'rxjs';
import { ChatService, ChatMessage, WritingMode } from '../services/chat.service';
import { ConversationService } from '../services/conversation.service';
import { DocumentService } from '../services/document.service';
import { AuthService } from '../services/auth.service';
import { SidebarComponent } from '../sidebar/sidebar.component';
import { ToastComponent } from '../toast/toast.component';
import { SettingsModalComponent, SettingsModal } from '../settings-modal/settings-modal.component';
import { Router } from '@angular/router';
import { MarkdownPipe } from '../pipes/markdown.pipe';
import { DocumentItem } from '../models/document.model';

@Component({
  selector: 'app-chat',
  imports: [
    FormsModule,
    MatIconModule,
    MatTooltipModule,
    SidebarComponent,
    ToastComponent,
    SettingsModalComponent,
    MarkdownPipe,
  ],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent implements OnInit, OnDestroy {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;
  @ViewChild('chatTextarea') private chatTextarea!: ElementRef<HTMLTextAreaElement>;

  private chatService = inject(ChatService);
  private conversationService = inject(ConversationService);
  private documentService = inject(DocumentService);
  private ngZone = inject(NgZone);
  private router = inject(Router);
  auth = inject(AuthService);
  private userScrolledUp = false;
  private wheelListener: ((e: WheelEvent) => void) | null = null;
  private touchStartY = 0;
  private touchMoveListener: ((e: TouchEvent) => void) | null = null;
  private touchStartListener: ((e: TouchEvent) => void) | null = null;
  private streamSub: Subscription | null = null;

  messages = signal<ChatMessage[]>([]);
  userInput = '';
  isStreaming = signal(false);
  writingMode = signal<WritingMode>('general');
  copiedIndex = signal<number | null>(null);
  modeDropdownOpen = signal(false);
  activeConversationId = signal<string | null>(null);

  // Documents attached to the current conversation (RAG sources).
  uploadedDocs = signal<DocumentItem[]>([]);
  uploadingFile = signal(false);
  expandedSourcesIndex = signal<number | null>(null);

  @ViewChild('sidebarRef') sidebarRef!: SidebarComponent;
  @ViewChild('toastRef') toastRef!: ToastComponent;
  @ViewChild('settingsModalRef') settingsModalRef!: SettingsModalComponent;
  @ViewChild('fileInput') fileInputRef!: ElementRef<HTMLInputElement>;

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

  async sendMessage() {
    const content = this.userInput.trim();
    if (!content || this.isStreaming()) return;

    const conversationId = await this.ensureConversation();

    const userMessage: ChatMessage = { role: 'user', content, timestamp: new Date() };
    this.messages.update((msgs) => [...msgs, userMessage]);
    this.userInput = '';
    this.resetTextarea();
    this.userScrolledUp = false;
    this.scheduleScroll();

    // Save user message to server
    this.saveMessageToServer(conversationId, 'user', content);

    const assistantMessage: ChatMessage = { role: 'assistant', content: '', timestamp: new Date() };
    this.messages.update((msgs) => [...msgs, assistantMessage]);
    this.isStreaming.set(true);

    this.streamSub = this.chatService
      .streamChat(this.messages().slice(0, -1), this.writingMode(), conversationId)
      .subscribe({
        next: (ev) => {
          if (ev.type === 'token') {
            this.messages.update((msgs) => {
              const updated = [...msgs];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + ev.content };
              return updated;
            });
            this.scheduleScroll();
          } else if (ev.type === 'sources') {
            this.messages.update((msgs) => {
              const updated = [...msgs];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, sources: ev.sources };
              return updated;
            });
          }
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
          const msgs = this.messages();
          const lastMsg = msgs[msgs.length - 1];
          this.messages.update((m) => {
            const updated = [...m];
            updated[updated.length - 1] = { ...lastMsg, timestamp: new Date() };
            return updated;
          });

          // Save assistant message and trigger title generation
          this.saveMessageToServer(conversationId, 'assistant', lastMsg.content);
          this.triggerTitleGeneration(conversationId);
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
    this.activeConversationId.set(null);
  }

  // ─── Conversation Management ─────────────────────

  onConversationSelected(id: string) {
    if (id === this.activeConversationId()) return;
    this.activeConversationId.set(id);
    this.expandedSourcesIndex.set(null);
    this.conversationService.getConversation(id).subscribe((detail) => {
      this.messages.set(
        detail.messages.map((m) => ({
          role: m.role as 'user' | 'assistant' | 'system',
          content: m.content,
          timestamp: new Date(m.createdAt),
        })),
      );
      this.scheduleScroll();
    });
    this.loadDocumentsForActiveConversation();
  }

  onNewChatRequested() {
    this.messages.set([]);
    this.activeConversationId.set(null);
    this.userInput = '';
    this.uploadedDocs.set([]);
    this.expandedSourcesIndex.set(null);
  }

  onSettingsModal(modal: SettingsModal) {
    this.settingsModalRef?.open(modal);
  }

  private ensureConversation(): Promise<string> {
    return new Promise((resolve) => {
      const id = this.activeConversationId();
      if (id) {
        resolve(id);
        return;
      }
      this.conversationService.createConversation().subscribe((conv) => {
        this.activeConversationId.set(conv.id);
        this.sidebarRef?.loadConversations();
        resolve(conv.id);
      });
    });
  }

  private saveMessageToServer(conversationId: string, role: string, content: string) {
    this.conversationService.saveMessage(conversationId, role, content).subscribe();
  }

  private triggerTitleGeneration(conversationId: string) {
    const conv = this.sidebarRef?.conversations().find((c) => c.id === conversationId);
    if (conv?.isTitleManual) return;

    const msgs = this.messages().map((m) => ({ role: m.role, content: m.content }));
    const currentTitle = conv?.title ?? '';

    this.conversationService.generateTitle(msgs, currentTitle).subscribe((result) => {
      const shouldUpdate = !conv?.titleGenCount || result.new_score > result.old_score;

      if (shouldUpdate) {
        this.conversationService.updateTitle(conversationId, result.title, true).subscribe(() => {
          this.sidebarRef?.loadConversations();
          this.toastRef?.show(`Chat renamed: "${result.title}"`, 'info');
        });
      }
    });
  }

  logout() {
    this.auth.logout();
    this.router.navigate(['/login']);
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

    const conversationId = this.activeConversationId() ?? undefined;
    this.streamSub = this.chatService
      .streamChat(kept, this.writingMode(), conversationId)
      .subscribe({
        next: (ev) => {
          if (ev.type === 'token') {
            this.messages.update((m) => {
              const updated = [...m];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + ev.content };
              return updated;
            });
            this.scheduleScroll();
          } else if (ev.type === 'sources') {
            this.messages.update((m) => {
              const updated = [...m];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, sources: ev.sources };
              return updated;
            });
          }
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

  // ─── Document Management (RAG) ────────────────────

  /** Trigger native file picker via hidden input. */
  openFilePicker() {
    if (!this.auth.isAuthenticated()) {
      this.toastRef?.show('Please log in to attach documents.', 'error');
      return;
    }
    this.fileInputRef?.nativeElement?.click();
  }

  /** Handle file selection from the hidden input. */
  async onFilePicked(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;

    const conversationId = await this.ensureConversation();
    this.uploadingFile.set(true);

    this.documentService.upload(conversationId, file).subscribe({
      next: (res) => {
        const optimistic: DocumentItem = {
          id: res.document_id,
          file_name: file.name,
          file_type: file.name.split('.').pop() ?? '',
          mime_type: file.type || 'application/octet-stream',
          file_size_bytes: file.size,
          status: res.status,
          chunk_count: res.chunk_count,
          created_at: new Date().toISOString(),
        };
        this.uploadedDocs.update((docs) => [...docs, optimistic]);
        this.toastRef?.show(`Attached "${file.name}" (${res.chunk_count} chunks).`, 'info');
      },
      error: (err) => {
        const detail = err?.error?.detail ?? err?.message ?? 'Upload failed';
        this.toastRef?.show(`Upload failed: ${detail}`, 'error');
        this.uploadingFile.set(false);
      },
      complete: () => this.uploadingFile.set(false),
    });
  }

  /** Remove a previously attached document for this conversation. */
  removeDocument(documentId: string) {
    this.documentService.delete(documentId).subscribe({
      next: () => {
        this.uploadedDocs.update((docs) => docs.filter((d) => d.id !== documentId));
      },
      error: (err) => {
        const detail = err?.error?.detail ?? err?.message ?? 'Delete failed';
        this.toastRef?.show(`Delete failed: ${detail}`, 'error');
      },
    });
  }

  /** Toggle the Sources accordion under an assistant message. */
  toggleSources(index: number) {
    this.expandedSourcesIndex.update((curr) => (curr === index ? null : index));
  }

  /** Format a chunk distance score for display (lower = closer). */
  formatDistance(distance: number): string {
    return distance.toFixed(3);
  }

  private loadDocumentsForActiveConversation() {
    const id = this.activeConversationId();
    if (!id || !this.auth.isAuthenticated()) {
      this.uploadedDocs.set([]);
      return;
    }
    this.documentService.list(id).subscribe({
      next: (docs) => this.uploadedDocs.set(docs),
      error: () => this.uploadedDocs.set([]),
    });
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

    // Touch: swipe up during streaming → pause auto-scroll
    this.touchStartListener = (e: TouchEvent) => {
      this.touchStartY = e.touches[0].clientY;
    };

    this.touchMoveListener = (e: TouchEvent) => {
      const deltaY = this.touchStartY - e.touches[0].clientY;

      // Swipe up (finger moves up, deltaY > 0 = scroll down in content, but finger drag up = scroll up visually)
      // Actually: finger drags DOWN (positive clientY change) = scrolling UP in content
      if (deltaY < -10 && this.isStreaming()) {
        this.userScrolledUp = true;
      }

      // Finger drags UP (scroll down) while paused → check if near bottom
      if (deltaY > 10 && this.userScrolledUp) {
        setTimeout(() => {
          if (this.isNearBottom()) {
            this.userScrolledUp = false;
          }
        }, 60);
      }
    };

    el.addEventListener('touchstart', this.touchStartListener, { passive: true });
    el.addEventListener('touchmove', this.touchMoveListener, { passive: true });
  }

  private detachScrollListener() {
    const el = this.messagesContainer?.nativeElement;
    if (!el) return;
    if (this.wheelListener) {
      el.removeEventListener('wheel', this.wheelListener);
    }
    if (this.touchStartListener) {
      el.removeEventListener('touchstart', this.touchStartListener);
    }
    if (this.touchMoveListener) {
      el.removeEventListener('touchmove', this.touchMoveListener);
    }
  }
}
