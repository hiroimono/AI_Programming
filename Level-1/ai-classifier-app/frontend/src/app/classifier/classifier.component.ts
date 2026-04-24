// classifier.component.ts  Main Classifier Component
// =====================================================
// This component is the single main screen of the application.
// User enters text -> clicks "Analyze" button -> AI shows the result.
//
// Angular 21 features used:
// - Signals (signal, computed)  reactive state management
// - inject()  functional DI instead of constructor-based DI

import { Component, inject, signal, computed, effect, OnInit, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KeyValuePipe } from '@angular/common';
import { ApiService } from '../services/api.service';
import {
  ClassificationResponse,
  FileClassificationResponse,
  BatchClassificationResponse,
  CategoryStats,
  OutputFile,
} from '../models/classification.model';

@Component({
  selector: 'app-classifier',
  imports: [FormsModule, KeyValuePipe],
  templateUrl: './classifier.component.html',
  styleUrl: './classifier.component.css',
})
export class ClassifierComponent implements OnInit, OnDestroy {
  private apiService = inject(ApiService);
  private fileWatcher: EventSource | null = null;

  // ---------------------
  // State (Signals)
  // ---------------------

  feedbackText = signal('');
  result = signal<ClassificationResponse | null>(null);
  isLoading = signal(false);
  loadingAction = signal<'analyze' | 'classify' | ''>('');
  error = signal('');

  // Tab state: text | file | manager
  activeTab = signal<'text' | 'file' | 'manager'>('text');
  isDragOver = signal(false);

  // File upload state (merged single + batch)
  selectedFiles = signal<File[]>([]);
  batchResult = signal<BatchClassificationResponse | null>(null);
  batchProgress = signal(0);
  currentFile = signal('');
  completedCount = signal(0);
  processingIndex = signal(-1);
  completedIndices = signal<Set<number>>(new Set());
  failedIndices = signal<Set<number>>(new Set());

  // Category stats (shown on file upload tab)
  categoryStats = signal<CategoryStats>({});

  // File Manager state
  managerFiles = signal<OutputFile[]>([]);
  managerLoading = signal(false);
  draggedFile = signal<OutputFile | null>(null);
  managerModalOpen = signal(false);
  generatingTests = signal(false);
  selectedManagerFiles = signal<Set<string>>(new Set());

  // File preview state
  previewOpen = signal(false);
  previewLoading = signal(false);
  previewFile = signal<{ filename: string; category: string; size: number; text: string } | null>(
    null,
  );

  // Config
  readonly allowedExtensions = ['.pdf', '.txt', '.docx', '.jpg', '.jpeg', '.png'];
  readonly maxFileSize = 10 * 1024 * 1024;
  readonly maxBatchFiles = 20;
  readonly allCategories = ['Complaint', 'Suggestion', 'Question', 'Praise'];

  // Computed
  canSubmit = computed(() => this.feedbackText().trim().length >= 10 && !this.isLoading());
  canSubmitBatch = computed(() => this.selectedFiles().length > 0 && !this.isLoading());

  confidencePercent = computed(() => {
    const r = this.result();
    return r ? Math.round(r.confidence * 100) : 0;
  });

  // Auto-scroll to the currently processing file card
  private scrollEffect = effect(() => {
    const idx = this.processingIndex();
    if (idx < 0) return;
    // Small delay so Angular renders the class change first
    setTimeout(() => {
      const el = document.querySelector('.batch-file-item.file-processing');
      el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 50);
  });

  ngOnInit(): void {
    this.loadCategoryStats();
    this.startFileWatcher();
  }

  // ---------------------
  // Sample texts (for testing)
  // ---------------------
  sampleTexts = [
    'My order has not arrived for 3 weeks and customer service is not helpful at all. Very bad experience.',
    'Could you add a dark mode to your app? It strains my eyes when using it at night.',
    'Your product is amazing! Kudos to your team, it gets better with every update.',
    'How do I change my billing date? I could not find it in the settings section.',
    'Your mobile app keeps crashing. I got 5 crashes after the last update. Needs urgent fix!',
  ];

  // ---------------------
  // Methods
  // ---------------------

  /** Switch between text, file and manager tabs */
  switchTab(tab: 'text' | 'file' | 'manager'): void {
    this.activeTab.set(tab);
    this.error.set('');
    if (tab === 'file') {
      this.loadCategoryStats();
    }
    if (tab === 'manager') {
      this.loadManagerFiles();
    }
  }

  /** Load category stats from backend */
  loadCategoryStats(): void {
    this.apiService.getCategoryStats().subscribe({
      next: (stats) => this.categoryStats.set(stats),
    });
  }

  /** Select a sample text and fill the textarea */
  useSample(text: string): void {
    this.activeTab.set('text');
    this.feedbackText.set(text);
    this.result.set(null);
    this.error.set('');
  }

  /** Handle file selection from input */
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.addFiles(Array.from(input.files));
    }
  }

  /** Handle drag over event */
  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver.set(true);
  }

  /** Handle drag leave event */
  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver.set(false);
  }

  /** Handle file drop */
  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver.set(false);

    if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
      this.addFiles(Array.from(event.dataTransfer.files));
    }
  }

  /** Send AI classification request (text mode) */
  classify(): void {
    if (!this.canSubmit()) return;

    this.isLoading.set(true);
    this.loadingAction.set('analyze');
    this.error.set('');
    this.result.set(null);

    this.apiService.classifyFeedback(this.feedbackText()).subscribe({
      next: (response) => {
        this.result.set(response);
        this.isLoading.set(false);
        this.loadingAction.set('');
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'An error occurred. Is the backend running?');
        this.isLoading.set(false);
        this.loadingAction.set('');
      },
    });
  }

  /** Classify text AND save as .txt file to output/{Category}/ */
  classifyAndSave(): void {
    if (!this.canSubmit()) return;

    this.isLoading.set(true);
    this.loadingAction.set('classify');
    this.error.set('');
    this.result.set(null);

    this.apiService.classifyAndSave(this.feedbackText()).subscribe({
      next: (response) => {
        this.result.set(response.classification);
        this.isLoading.set(false);
        this.loadingAction.set('');
        this.loadCategoryStats();
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'An error occurred. Is the backend running?');
        this.isLoading.set(false);
        this.loadingAction.set('');
      },
    });
  }

  // ---------------------
  // File upload methods
  // ---------------------

  /** Add files to batch list with validation */
  addFiles(files: File[]): void {
    this.error.set('');
    const current = this.selectedFiles();
    const remaining = this.maxBatchFiles - current.length;

    if (remaining <= 0) {
      this.error.set(`Maximum ${this.maxBatchFiles} files allowed.`);
      return;
    }

    const toAdd: File[] = [];
    for (const file of files.slice(0, remaining)) {
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      if (!this.allowedExtensions.includes(ext)) {
        this.error.set(
          `Skipped '${file.name}': unsupported type. Allowed: ${this.allowedExtensions.join(', ')}`,
        );
        continue;
      }
      if (file.size > this.maxFileSize) {
        this.error.set(`Skipped '${file.name}': too large (max 10 MB).`);
        continue;
      }
      // Avoid duplicates by name
      if (!current.some((f) => f.name === file.name)) {
        toAdd.push(file);
      }
    }

    this.selectedFiles.set([...current, ...toAdd]);
  }

  /** Remove a file from batch list */
  removeBatchFile(index: number): void {
    const files = [...this.selectedFiles()];
    files.splice(index, 1);
    this.selectedFiles.set(files);
    if (files.length === 0) {
      this.batchResult.set(null);
    }
  }

  /** Clear all batch files */
  clearBatch(): void {
    this.selectedFiles.set([]);
    this.batchResult.set(null);
    this.batchProgress.set(0);
    this.currentFile.set('');
    this.completedCount.set(0);
    this.error.set('');
  }

  /** Send batch classification request via SSE stream */
  classifyBatch(): void {
    const files = this.selectedFiles();
    if (files.length === 0 || !this.canSubmitBatch()) return;

    this.isLoading.set(true);
    this.error.set('');
    this.batchResult.set(null);
    this.batchProgress.set(0);
    this.completedCount.set(0);
    this.processingIndex.set(0);
    this.completedIndices.set(new Set());
    this.failedIndices.set(new Set());
    this.currentFile.set(files[0]?.name || '');

    const { promise } = this.apiService.classifyFilesStream(files, (event) => {
      // Mark current file as completed or failed
      const done = new Set(this.completedIndices());
      const failed = new Set(this.failedIndices());
      if (event.error) {
        failed.add(event.index);
        this.failedIndices.set(failed);
      } else {
        done.add(event.index);
        this.completedIndices.set(done);
      }

      // Move processing indicator to next file
      const nextIndex = event.index + 1;
      this.processingIndex.set(nextIndex < event.total ? nextIndex : -1);

      const completed = event.index + 1;
      const pct = Math.round((completed / event.total) * 100);
      this.completedCount.set(completed);
      this.batchProgress.set(pct);
      this.currentFile.set(event.filename);
    });

    promise
      .then((response) => {
        this.batchResult.set(response);
        this.batchProgress.set(100);
        this.currentFile.set('');
        this.processingIndex.set(-1);
        this.isLoading.set(false);
        this.loadCategoryStats();
      })
      .catch((err) => {
        this.error.set(err.message || 'An error occurred processing files.');
        this.batchProgress.set(0);
        this.currentFile.set('');
        this.processingIndex.set(-1);
        this.isLoading.set(false);
      });
  }

  /** Classify a single file from the list (per-file button) */
  classifySingleFile(index: number): void {
    const file = this.selectedFiles()[index];
    if (!file || this.isLoading()) return;

    this.isLoading.set(true);
    this.error.set('');
    this.currentFile.set(file.name);
    this.batchProgress.set(0);
    this.completedCount.set(0);

    const { promise } = this.apiService.classifyFilesStream([file], (event) => {
      this.batchProgress.set(Math.round(((event.index + 1) / event.total) * 100));
    });

    promise
      .then((response) => {
        // Merge result into existing batch result
        const existing = this.batchResult();
        if (existing) {
          this.batchResult.set({
            results: [...existing.results, ...response.results],
            errors: [...existing.errors, ...response.errors],
            summary: { ...existing.summary, ...response.summary },
          });
        } else {
          this.batchResult.set(response);
        }
        // Remove the classified file from queue
        const files = [...this.selectedFiles()];
        files.splice(index, 1);
        this.selectedFiles.set(files);
        this.batchProgress.set(100);
        this.currentFile.set('');
        this.isLoading.set(false);
        this.loadCategoryStats();
      })
      .catch((err) => {
        this.error.set(err.message || 'Failed to classify file.');
        this.batchProgress.set(0);
        this.currentFile.set('');
        this.isLoading.set(false);
      });
  }

  // ---------------------
  // File Manager methods
  // ---------------------

  /** Load all classified files from output */
  loadManagerFiles(): void {
    this.managerLoading.set(true);
    this.apiService.getFiles().subscribe({
      next: (files) => {
        this.managerFiles.set(files);
        this.managerLoading.set(false);
      },
      error: () => {
        this.managerFiles.set([]);
        this.managerLoading.set(false);
      },
    });
  }

  /** Get files for a specific category (File Manager) */
  getFilesForCategory(category: string): OutputFile[] {
    return this.managerFiles().filter((f) => f.category === category);
  }

  /** Delete a file from File Manager */
  deleteManagerFile(file: OutputFile): void {
    this.apiService.deleteFile(file.category, file.filename).subscribe({
      next: () => {
        this.managerFiles.set(this.managerFiles().filter((f) => f !== file));
        this.loadCategoryStats();
      },
      error: () => this.error.set(`Failed to delete '${file.filename}'.`),
    });
  }

  /** Unique key for a file (used in selection set) */
  private fileKey(file: OutputFile): string {
    return `${file.category}::${file.filename}`;
  }

  /** Toggle selection of a single file */
  toggleFileSelect(file: OutputFile): void {
    const key = this.fileKey(file);
    const set = new Set(this.selectedManagerFiles());
    if (set.has(key)) {
      set.delete(key);
    } else {
      set.add(key);
    }
    this.selectedManagerFiles.set(set);
  }

  /** Check if a file is selected */
  isFileSelected(file: OutputFile): boolean {
    return this.selectedManagerFiles().has(this.fileKey(file));
  }

  /** Toggle select all files in a category */
  toggleSelectCategory(category: string): void {
    const catFiles = this.getFilesForCategory(category);
    const set = new Set(this.selectedManagerFiles());
    const allSelected = catFiles.every((f) => set.has(this.fileKey(f)));

    for (const f of catFiles) {
      if (allSelected) {
        set.delete(this.fileKey(f));
      } else {
        set.add(this.fileKey(f));
      }
    }
    this.selectedManagerFiles.set(set);
  }

  /** Check if all files in a category are selected */
  isCategoryAllSelected(category: string): boolean {
    const catFiles = this.getFilesForCategory(category);
    if (catFiles.length === 0) return false;
    return catFiles.every((f) => this.selectedManagerFiles().has(this.fileKey(f)));
  }

  /** Check if some (but not all) files in a category are selected */
  isCategorySomeSelected(category: string): boolean {
    const catFiles = this.getFilesForCategory(category);
    const set = this.selectedManagerFiles();
    const selectedCount = catFiles.filter((f) => set.has(this.fileKey(f))).length;
    return selectedCount > 0 && selectedCount < catFiles.length;
  }

  /** Get count of selected files in a category */
  getSelectedCountForCategory(category: string): number {
    const catFiles = this.getFilesForCategory(category);
    const set = this.selectedManagerFiles();
    return catFiles.filter((f) => set.has(this.fileKey(f))).length;
  }

  /** Bulk delete all selected files */
  deleteSelectedFiles(): void {
    const set = this.selectedManagerFiles();
    if (set.size === 0) return;

    const items = Array.from(set).map((key) => {
      const [category, filename] = key.split('::');
      return { category, filename };
    });

    this.apiService.bulkDeleteFiles(items).subscribe({
      next: (res) => {
        const deletedSet = new Set(res.deleted);
        this.managerFiles.set(this.managerFiles().filter((f) => !deletedSet.has(f.filename)));
        this.selectedManagerFiles.set(new Set());
        this.loadCategoryStats();
        if (res.failed.length > 0) {
          this.error.set(`Failed to delete ${res.failed.length} file(s).`);
        }
      },
      error: () => this.error.set('Failed to delete selected files.'),
    });
  }

  /** Clear selection */
  clearSelection(): void {
    this.selectedManagerFiles.set(new Set());
  }

  /** Open file preview modal (triggered by fast double-click) */
  openFilePreview(file: OutputFile): void {
    this.previewOpen.set(true);
    this.previewLoading.set(true);
    this.previewFile.set(null);
    this.apiService.previewFile(file.category, file.filename).subscribe({
      next: (data) => {
        this.previewFile.set(data);
        this.previewLoading.set(false);
      },
      error: () => {
        this.previewFile.set({
          filename: file.filename,
          category: file.category,
          size: file.size,
          text: '(Failed to load preview)',
        });
        this.previewLoading.set(false);
      },
    });
  }

  /** Close file preview modal */
  closeFilePreview(): void {
    this.previewOpen.set(false);
    this.previewFile.set(null);
  }

  /** Generate random test files and download as ZIP */
  generateTestFiles(): void {
    this.generatingTests.set(true);
    this.error.set('');
    this.apiService.generateTestFiles(40).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'test-files.zip';
        a.click();
        URL.revokeObjectURL(url);
        this.generatingTests.set(false);
      },
      error: () => {
        this.error.set('Failed to generate test files.');
        this.generatingTests.set(false);
      },
    });
  }

  /** Start drag in File Manager */
  onManagerDragStart(event: DragEvent, file: OutputFile): void {
    this.draggedFile.set(file);
    event.dataTransfer?.setData('text/plain', JSON.stringify(file));
  }

  /** Drag over a category column */
  onCategoryDragOver(event: DragEvent): void {
    event.preventDefault();
  }

  /** Drop file onto a category column */
  onCategoryDrop(event: DragEvent, targetCategory: string): void {
    event.preventDefault();
    const file = this.draggedFile();
    if (!file || file.category === targetCategory) {
      this.draggedFile.set(null);
      return;
    }

    this.apiService.moveFile(file.filename, file.category, targetCategory).subscribe({
      next: () => {
        // Update local state
        const updated = this.managerFiles().map((f) =>
          f === file ? { ...f, category: targetCategory } : f,
        );
        this.managerFiles.set(updated);
        this.draggedFile.set(null);
        this.loadCategoryStats();
      },
      error: () => {
        this.error.set(`Failed to move '${file.filename}'.`);
        this.draggedFile.set(null);
      },
    });
  }

  /** Open expanded modal */
  openManagerModal(): void {
    this.managerModalOpen.set(true);
  }

  /** Close expanded modal */
  closeManagerModal(): void {
    this.managerModalOpen.set(false);
  }

  /** Close modal on backdrop click */
  onModalBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('modal-backdrop')) {
      this.closeManagerModal();
    }
  }

  // ---------------------
  // File watcher (SSE)
  // ---------------------

  /** Start watching output directory for real-time changes */
  private startFileWatcher(): void {
    this.stopFileWatcher();
    this.fileWatcher = this.apiService.watchFileChanges(() => {
      this.loadManagerFiles();
      this.loadCategoryStats();
    });
  }

  /** Stop watching (when leaving manager tab or destroying component) */
  private stopFileWatcher(): void {
    if (this.fileWatcher) {
      this.fileWatcher.close();
      this.fileWatcher = null;
    }
  }

  ngOnDestroy(): void {
    this.stopFileWatcher();
  }

  /** Download organized ZIP results */
  downloadResults(): void {
    const result = this.batchResult();
    if (!result) return;

    this.apiService.downloadResults().subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'classified-results.zip';
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: () => {
        this.error.set('Failed to download results.');
      },
    });
  }

  /** Clear the form */
  reset(): void {
    this.feedbackText.set('');
    this.result.set(null);
    this.selectedFiles.set([]);
    this.batchResult.set(null);
    this.batchProgress.set(0);
    this.currentFile.set('');
    this.completedCount.set(0);
    this.error.set('');
  }

  // ---------------------
  // Helper methods (used in template)
  // ---------------------

  /** Color code for category */
  getCategoryColor(category: string): string {
    const colors: Record<string, string> = {
      Complaint: '#ef4444',
      Suggestion: '#3b82f6',
      Question: '#f59e0b',
      Praise: '#22c55e',
    };
    return colors[category] || '#6b7280';
  }

  /** Emoji for sentiment */
  getSentimentEmoji(sentiment: string): string {
    const emojis: Record<string, string> = {
      Positive: '😊',
      Negative: '😞',
      Neutral: '😐',
    };
    return emojis[sentiment] || '❓';
  }

  /** Confidence bar color */
  getConfidenceColor(percent?: number): string {
    const pct = percent ?? this.confidencePercent();
    if (pct >= 80) return '#22c55e';
    if (pct >= 50) return '#f59e0b';
    return '#ef4444';
  }

  /** Format file size for display */
  formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  /** Get icon for file type */
  getFileIcon(filename: string): string {
    const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
    const icons: Record<string, string> = {
      '.pdf': '�',
      '.txt': '📋',
      '.docx': '📘',
      '.jpg': '🎨',
      '.jpeg': '🎨',
      '.png': '🎨',
    };
    return icons[ext] || '📎';
  }

  /** Get icon for category */
  getCategoryIcon(category: string): string {
    const icons: Record<string, string> = {
      Complaint: '🚨',
      Suggestion: '💡',
      Question: '❓',
      Praise: '⭐',
    };
    return icons[category] || '📌';
  }

  /** Get file type label */
  getFileTypeLabel(filename: string): string {
    const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
    const labels: Record<string, string> = {
      '.pdf': 'PDF',
      '.txt': 'TXT',
      '.docx': 'DOCX',
      '.jpg': 'JPG',
      '.jpeg': 'JPEG',
      '.png': 'PNG',
    };
    return labels[ext] || 'FILE';
  }

  /** Get CSS class for file type badge */
  getFileTypeClass(filename: string): string {
    const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
    if (['.jpg', '.jpeg', '.png'].includes(ext)) return 'type-image';
    if (ext === '.pdf') return 'type-pdf';
    if (ext === '.docx') return 'type-docx';
    return 'type-txt';
  }
}
