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
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { Subscription, forkJoin } from 'rxjs';
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
  private sanitizer = inject(DomSanitizer);
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

  // Documents the user has staged for the *next* message they send.
  // After send, these are copied onto the user message's `attachments`
  // field and cleared from this signal — so chips stay anchored to the
  // question they were attached to, not to the conversation overall.
  pendingDocs = signal<DocumentItem[]>([]);
  uploadingFile = signal(false);
  expandedSourcesIndex = signal<number | null>(null);

  // Preview modal state. previewDoc is the chip the user clicked; the
  // original file bytes are fetched as a blob and rendered inline based
  // on mime-type (PDF → iframe, image → img, text → <pre>). The object
  // URL is revoked on close to avoid memory leaks.
  previewDoc = signal<DocumentItem | null>(null);
  previewLoading = signal(false);
  previewError = signal<string | null>(null);
  previewKind = signal<'pdf' | 'image' | 'text' | 'unsupported' | null>(null);
  previewSafeUrl = signal<SafeResourceUrl | null>(null);
  previewText = signal<string | null>(null);
  private previewObjectUrl: string | null = null;

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
    this.releasePreviewUrl();
  }

  async sendMessage() {
    const content = this.userInput.trim();
    if (!content || this.isStreaming()) return;

    const conversationId = await this.ensureConversation();

    // Snapshot pending attachments onto the outgoing user message, then
    // clear them from the composer so the next message starts blank.
    const attachments = this.pendingDocs();
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date(),
      attachments: attachments.length > 0 ? attachments : undefined,
    };
    this.messages.update((msgs) => [...msgs, userMessage]);
    this.pendingDocs.set([]);
    this.userInput = '';
    this.resetTextarea();
    this.userScrolledUp = false;
    this.scheduleScroll();

    // Save user message to server (with attached doc IDs so the chips can be
    // rehydrated when the conversation is reopened from the sidebar).
    this.saveMessageToServer(
      conversationId,
      'user',
      content,
      attachments.map((a) => a.id),
    );

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
    // Clear staged uploads when switching conversations — attachments
    // belong to the message they were sent with, not to the conversation.
    this.pendingDocs.set([]);

    // Load the conversation transcript *and* the conversation's known
    // documents in parallel, then stitch attachment chips back onto each
    // user message by joining `attachedDocumentIds` against the doc list.
    forkJoin({
      detail: this.conversationService.getConversation(id),
      docs: this.documentService.list(id),
    }).subscribe(({ detail, docs }) => {
      const docMap = new Map(docs.map((d) => [d.id, d]));
      this.messages.set(
        detail.messages.map((m) => {
          const attachments = (m.attachedDocumentIds ?? [])
            .map((docId) => docMap.get(docId))
            .filter((d): d is NonNullable<typeof d> => !!d);
          return {
            role: m.role as 'user' | 'assistant' | 'system',
            content: m.content,
            timestamp: new Date(m.createdAt),
            attachments: attachments.length > 0 ? attachments : undefined,
          };
        }),
      );
      this.scheduleScroll();
    });
  }

  onNewChatRequested() {
    this.messages.set([]);
    this.activeConversationId.set(null);
    this.userInput = '';
    this.pendingDocs.set([]);
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

  private saveMessageToServer(
    conversationId: string,
    role: string,
    content: string,
    attachedDocumentIds?: string[],
  ) {
    this.conversationService
      .saveMessage(conversationId, role, content, attachedDocumentIds)
      .subscribe();
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

    // Restore the attachments that were originally sent with this message,
    // so they ride along with the re-edited question. We dedupe against
    // anything already pending (e.g. a fresh upload before clicking edit).
    if (msg.attachments?.length) {
      const existingIds = new Set(this.pendingDocs().map((d) => d.id));
      const restored = msg.attachments.filter((d) => !existingIds.has(d.id));
      if (restored.length) {
        this.pendingDocs.update((curr) => [...curr, ...restored]);
      }
    }

    // Remove this message and everything after it
    this.messages.update((msgs) => msgs.slice(0, index));

    // Defer resize + focus until after Angular flushes the new ngModel value
    // into the textarea. Otherwise autoResize() runs against the stale empty
    // value, leaves the textarea at min-height, and the long content scrolls —
    // making the first line look like it's hidden behind the attachment chip.
    setTimeout(() => {
      const ta = this.chatTextarea?.nativeElement;
      if (!ta) return;
      this.autoResize();
      ta.scrollTop = 0;
      ta.focus();
      // Place caret at end so user can keep typing
      const len = ta.value.length;
      ta.setSelectionRange(len, len);
    });
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
        this.pendingDocs.update((docs) => [...docs, optimistic]);
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

  /** Remove a staged (not-yet-sent) document, also deleting it from
   *  rag-service so it can't be retrieved later by mistake. */
  removePendingDocument(documentId: string) {
    this.documentService.delete(documentId).subscribe({
      next: () => {
        this.pendingDocs.update((docs) => docs.filter((d) => d.id !== documentId));
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

  /**
   * Collapse raw chunk-level citations down to one row per distinct document.
   * The middle-of-document text excerpts the retriever returns are usually
   * meaningless to a human reader, so we just expose the source documents
   * with a count of how many passages were used.
   */
  getDistinctSources(msg: ChatMessage): {
    document_id: string;
    filename: string;
    count: number;
    bestDistance: number;
  }[] {
    if (!msg.sources?.length) return [];
    const byDoc = new Map<
      string,
      { document_id: string; filename: string; count: number; bestDistance: number }
    >();
    for (const s of msg.sources) {
      const existing = byDoc.get(s.document_id);
      if (existing) {
        existing.count++;
        if (s.distance < existing.bestDistance) existing.bestDistance = s.distance;
      } else {
        byDoc.set(s.document_id, {
          document_id: s.document_id,
          filename: s.document_filename,
          count: 1,
          bestDistance: s.distance,
        });
      }
    }
    return Array.from(byDoc.values()).sort((a, b) => a.bestDistance - b.bestDistance);
  }

  /**
   * Decide whether the Sources panel is worth showing. We hide it when
   * every cited document is one the user already attached to the
   * immediately preceding user message — the user knows where the answer
   * came from, no point in restating the obvious. We do show the panel
   * when any cited document is *not* in that attachment set (e.g., an
   * earlier conversation upload, or in future, a web result).
   */
  shouldShowSources(msgIndex: number): boolean {
    const msg = this.messages()[msgIndex];
    if (!msg?.sources?.length) return false;

    // Walk backwards to find the user message this assistant message replies to.
    let userMsg: ChatMessage | undefined;
    for (let i = msgIndex - 1; i >= 0; i--) {
      const m = this.messages()[i];
      if (m.role === 'user') {
        userMsg = m;
        break;
      }
    }
    const attachedIds = new Set((userMsg?.attachments ?? []).map((d) => d.id));
    if (attachedIds.size === 0) return true; // No anchor info → be safe, show.

    const distinct = this.getDistinctSources(msg);
    // If every distinct source doc is one the user just attached, hide.
    return distinct.some((d) => !attachedIds.has(d.document_id));
  }

  /** Format file size as KB/MB/GB for chip tooltip. */
  formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
  }

  /** Open the preview modal for a document chip. Streams the original
   *  file bytes and decides how to render based on content-type. */
  openPreview(doc: DocumentItem) {
    // Wipe any prior preview state (including URL from a previous open).
    this.releasePreviewUrl();
    this.previewDoc.set(doc);
    this.previewError.set(null);
    this.previewKind.set(null);
    this.previewSafeUrl.set(null);
    this.previewText.set(null);
    this.previewLoading.set(true);

    this.documentService.getFileBlob(doc.id).subscribe({
      next: ({ blob, contentType }) => {
        const kind = this.classifyMime(contentType);
        this.previewKind.set(kind);

        if (kind === 'text') {
          // Read as UTF-8; if decoding fails the user still sees a usable hex-ish
          // fallback. Falls through to text branch in the template.
          blob
            .text()
            .then((txt) => {
              this.previewText.set(txt);
              this.previewLoading.set(false);
            })
            .catch(() => {
              this.previewError.set('Unable to decode file as text.');
              this.previewLoading.set(false);
            });
          return;
        }

        // pdf / image / unsupported all use an object URL: iframe, img tag,
        // or download anchor respectively.
        const url = URL.createObjectURL(blob);
        this.previewObjectUrl = url;
        this.previewSafeUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
        this.previewLoading.set(false);
      },
      error: (err) => {
        const detail = err?.error?.detail ?? err?.message ?? 'Failed to load preview';
        this.previewError.set(detail);
        this.previewLoading.set(false);
      },
    });
  }

  closePreview() {
    this.releasePreviewUrl();
    this.previewDoc.set(null);
    this.previewKind.set(null);
    this.previewSafeUrl.set(null);
    this.previewText.set(null);
    this.previewError.set(null);
    this.previewLoading.set(false);
  }

  /** Trigger a browser download of the currently-previewed document.
   *  Used as the primary action for unsupported types and as a secondary
   *  action in the header for any kind. */
  downloadPreview() {
    const doc = this.previewDoc();
    if (!doc || !this.previewObjectUrl) return;
    const a = document.createElement('a');
    a.href = this.previewObjectUrl;
    a.download = doc.file_name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  private classifyMime(contentType: string): 'pdf' | 'image' | 'text' | 'unsupported' {
    const ct = (contentType || '').toLowerCase().split(';')[0].trim();
    if (ct === 'application/pdf') return 'pdf';
    if (ct.startsWith('image/')) return 'image';
    if (ct.startsWith('text/') || ct === 'application/json' || ct === 'application/xml') {
      return 'text';
    }
    return 'unsupported';
  }

  private releasePreviewUrl() {
    if (this.previewObjectUrl) {
      URL.revokeObjectURL(this.previewObjectUrl);
      this.previewObjectUrl = null;
    }
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
