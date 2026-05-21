import {
  Component,
  inject,
  signal,
  computed,
  output,
  OnInit,
  OnDestroy,
  HostListener,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subject, debounceTime, distinctUntilChanged, switchMap, of, takeUntil } from 'rxjs';
import { ConversationService } from '../services/conversation.service';
import { AuthService } from '../services/auth.service';
import { Conversation } from '../models/conversation.model';
import { SettingsModal } from '../settings-modal/settings-modal.component';

@Component({
  selector: 'app-sidebar',
  imports: [FormsModule, MatIconModule, MatTooltipModule],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent implements OnInit, OnDestroy {
  private conversationService = inject(ConversationService);
  auth = inject(AuthService);
  private destroy$ = new Subject<void>();
  private searchSubject$ = new Subject<string>();

  // State
  expanded = signal(true);
  conversations = signal<Conversation[]>([]);
  activeConversationId = signal<string | null>(null);
  searchQuery = signal('');
  selectMode = signal(false);
  selectedIds = signal<Set<string>>(new Set());
  menuOpenId = signal<string | null>(null);
  renamingId = signal<string | null>(null);
  renameValue = signal('');
  settingsOpen = signal(false);

  // Outputs
  conversationSelected = output<string>();
  newChatRequested = output<void>();
  settingsModalRequested = output<SettingsModal>();
  logoutRequested = output<void>();

  selectedCount = computed(() => this.selectedIds().size);

  private readonly COLLAPSE_BREAKPOINT = 768;

  ngOnInit() {
    this.checkScreenWidth();
    this.loadConversations();

    this.searchSubject$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((q) =>
          q.trim()
            ? this.conversationService.searchConversations(q)
            : this.conversationService.getConversations(),
        ),
        takeUntil(this.destroy$),
      )
      .subscribe((results) => this.conversations.set(results));
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }

  @HostListener('window:resize')
  onResize() {
    this.checkScreenWidth();
  }

  private checkScreenWidth() {
    if (window.innerWidth < this.COLLAPSE_BREAKPOINT) {
      this.expanded.set(false);
    }
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.context-menu') && !target.closest('.menu-trigger')) {
      this.menuOpenId.set(null);
    }
    if (!target.closest('.settings-panel') && !target.closest('.settings-trigger')) {
      this.settingsOpen.set(false);
    }
    // Collapse sidebar on outside click (mobile)
    if (
      this.expanded() &&
      window.innerWidth < this.COLLAPSE_BREAKPOINT &&
      !target.closest('.sidebar')
    ) {
      this.expanded.set(false);
    }
  }

  toggleSidebar() {
    this.expanded.update((v) => !v);
  }

  loadConversations() {
    this.conversationService
      .getConversations()
      .pipe(takeUntil(this.destroy$))
      .subscribe((data) => this.conversations.set(data));
  }

  onSearch(query: string) {
    this.searchQuery.set(query);
    this.searchSubject$.next(query);
  }

  selectConversation(id: string) {
    if (this.selectMode()) {
      this.toggleSelection(id);
      return;
    }
    this.activeConversationId.set(id);
    this.conversationSelected.emit(id);
  }

  createNewChat() {
    this.activeConversationId.set(null);
    this.newChatRequested.emit();
  }

  // ─── Context Menu ────────────────────────────────

  toggleMenu(event: MouseEvent, id: string) {
    event.stopPropagation();
    this.menuOpenId.update((current) => (current === id ? null : id));
  }

  startRename(id: string) {
    const conv = this.conversations().find((c) => c.id === id);
    if (!conv) return;
    this.renameValue.set(conv.title);
    this.renamingId.set(id);
    this.menuOpenId.set(null);
  }

  confirmRename(id: string) {
    const newTitle = this.renameValue().trim();
    if (!newTitle) return;

    this.conversationService
      .updateTitle(id, newTitle)
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        this.conversations.update((list) =>
          list.map((c) => (c.id === id ? { ...c, title: newTitle, isTitleManual: true } : c)),
        );
        this.renamingId.set(null);
      });
  }

  cancelRename() {
    this.renamingId.set(null);
  }

  deleteConversation(id: string) {
    this.menuOpenId.set(null);
    this.conversationService
      .deleteConversation(id)
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        this.conversations.update((list) => list.filter((c) => c.id !== id));
        if (this.activeConversationId() === id) {
          this.activeConversationId.set(null);
          this.newChatRequested.emit();
        }
      });
  }

  // ─── Multi-select ────────────────────────────────

  toggleSelectMode() {
    this.selectMode.update((v) => !v);
    if (!this.selectMode()) {
      this.selectedIds.set(new Set());
    }
  }

  toggleSelection(id: string) {
    this.selectedIds.update((set) => {
      const next = new Set(set);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  deleteSelected() {
    const ids = [...this.selectedIds()];
    if (ids.length === 0) return;

    this.conversationService
      .batchDelete(ids)
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        this.conversations.update((list) => list.filter((c) => !ids.includes(c.id)));
        this.selectedIds.set(new Set());
        this.selectMode.set(false);
        if (this.activeConversationId() && ids.includes(this.activeConversationId()!)) {
          this.activeConversationId.set(null);
          this.newChatRequested.emit();
        }
      });
  }

  // ─── Settings ────────────────────────────────────

  toggleSettings() {
    this.settingsOpen.update((v) => !v);
  }

  openSettingsModal(modal: SettingsModal) {
    this.settingsOpen.set(false);
    this.settingsModalRequested.emit(modal);
  }

  // ─── Helpers ─────────────────────────────────────

  formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
}
