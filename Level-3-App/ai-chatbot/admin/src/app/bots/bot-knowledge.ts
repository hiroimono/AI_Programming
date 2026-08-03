import { Component, Input, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { DocumentItem } from '../models/document.model';
import { DocumentService } from '../services/document.service';
import { ToastService } from '../services/toast.service';

/**
 * Knowledge tab: upload training files and manage a bot's document list.
 *
 * Upload is synchronous on the backend (parse -> chunk -> embed), so the
 * returned row already carries its final status + chunk_count. We surface the
 * "ready but 0 chunks" case explicitly: the file was accepted but produced no
 * indexable text (too short/empty), so the bot can't answer from it.
 */
@Component({
  selector: 'app-bot-knowledge',
  imports: [
    DatePipe,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressBarModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './bot-knowledge.html',
  styleUrl: './bot-knowledge.scss',
})
export class BotKnowledgeComponent implements OnInit {
  @Input({ required: true }) botId!: string;

  private docService = inject(DocumentService);
  private toast = inject(ToastService);

  readonly docs = signal<DocumentItem[]>([]);
  readonly loading = signal(true);
  readonly uploading = signal(false);

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.docService.list(this.botId).subscribe({
      next: (docs) => {
        this.docs.set(docs);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.toast.error('Failed to load documents.');
      },
    });
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    this.uploading.set(true);
    this.docService.upload(this.botId, file).subscribe({
      next: (doc) => {
        this.uploading.set(false);
        input.value = '';
        this.docs.update((list) => [doc, ...list]);
        if (this.isEmptyIndex(doc)) {
          this.toast.error('Uploaded, but indexed 0 chunks — the file may be too short.');
        } else {
          this.toast.success('Document uploaded and indexed.');
        }
      },
      error: (err) => {
        this.uploading.set(false);
        input.value = '';
        this.toast.error(this.errorMessage(err, 'Upload failed.'));
      },
    });
  }

  confirmDelete(doc: DocumentItem): void {
    const ok = window.confirm(`Remove "${doc.file_name}" from the knowledge base?`);
    if (!ok) {
      return;
    }
    this.docService.remove(this.botId, doc.id).subscribe({
      next: () => {
        this.docs.update((list) => list.filter((d) => d.id !== doc.id));
        this.toast.success('Document removed.');
      },
      error: () => this.toast.error('Could not remove document.'),
    });
  }

  isEmptyIndex(doc: DocumentItem): boolean {
    return doc.status === 'ready' && doc.chunk_count === 0;
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) {
      return `${bytes} B`;
    }
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  private errorMessage(err: unknown, fallback: string): string {
    const detail = (err as { error?: { detail?: unknown } })?.error?.detail;
    return typeof detail === 'string' ? detail : fallback;
  }
}
