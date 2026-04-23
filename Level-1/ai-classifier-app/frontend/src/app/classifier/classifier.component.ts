// classifier.component.ts  Main Classifier Component
// =====================================================
// This component is the single main screen of the application.
// User enters text -> clicks "Analyze" button -> AI shows the result.
//
// Angular 21 features used:
// - Signals (signal, computed)  reactive state management
// - inject()  functional DI instead of constructor-based DI

import { Component, inject, signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../services/api.service';
import { ClassificationResponse, FileClassificationResponse } from '../models/classification.model';

@Component({
  selector: 'app-classifier',
  imports: [FormsModule],
  templateUrl: './classifier.component.html',
  styleUrl: './classifier.component.css',
})
export class ClassifierComponent {
  private apiService = inject(ApiService);

  // ---------------------
  // State (Signals)
  // ---------------------

  feedbackText = signal('');
  result = signal<ClassificationResponse | null>(null);
  isLoading = signal(false);
  error = signal('');

  // File upload state
  activeTab = signal<'text' | 'file'>('text');
  selectedFile = signal<File | null>(null);
  fileResult = signal<FileClassificationResponse | null>(null);
  isDragOver = signal(false);

  // Allowed file types
  readonly allowedExtensions = ['.pdf', '.txt', '.docx', '.jpg', '.jpeg', '.png'];
  readonly maxFileSize = 10 * 1024 * 1024; // 10 MB

  // Computed
  canSubmit = computed(() => this.feedbackText().trim().length >= 10 && !this.isLoading());
  canSubmitFile = computed(() => this.selectedFile() !== null && !this.isLoading());

  confidencePercent = computed(() => {
    const r = this.result();
    return r ? Math.round(r.confidence * 100) : 0;
  });

  fileConfidencePercent = computed(() => {
    const r = this.fileResult();
    return r ? Math.round(r.classification.confidence * 100) : 0;
  });

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

  /** Switch between text and file tabs */
  switchTab(tab: 'text' | 'file'): void {
    this.activeTab.set(tab);
    this.error.set('');
  }

  /** Select a sample text and fill the textarea */
  useSample(text: string): void {
    this.activeTab.set('text');
    this.feedbackText.set(text);
    this.result.set(null);
    this.fileResult.set(null);
    this.error.set('');
  }

  /** Handle file selection from input */
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.setFile(input.files[0]);
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
      this.setFile(event.dataTransfer.files[0]);
    }
  }

  /** Validate and set the selected file */
  private setFile(file: File): void {
    this.error.set('');
    this.fileResult.set(null);

    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!this.allowedExtensions.includes(ext)) {
      this.error.set(
        `Unsupported file type: '${ext}'. Allowed: ${this.allowedExtensions.join(', ')}`,
      );
      this.selectedFile.set(null);
      return;
    }

    if (file.size > this.maxFileSize) {
      this.error.set(`File too large: ${(file.size / (1024 * 1024)).toFixed(1)} MB. Max: 10 MB`);
      this.selectedFile.set(null);
      return;
    }

    this.selectedFile.set(file);
  }

  /** Remove selected file */
  removeFile(): void {
    this.selectedFile.set(null);
    this.fileResult.set(null);
    this.error.set('');
  }

  /** Send AI classification request (text mode) */
  classify(): void {
    if (!this.canSubmit()) return;

    this.isLoading.set(true);
    this.error.set('');
    this.result.set(null);

    this.apiService.classifyFeedback(this.feedbackText()).subscribe({
      next: (response) => {
        this.result.set(response);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'An error occurred. Is the backend running?');
        this.isLoading.set(false);
      },
    });
  }

  /** Send AI classification request (file mode) */
  classifyFile(): void {
    const file = this.selectedFile();
    if (!file || !this.canSubmitFile()) return;

    this.isLoading.set(true);
    this.error.set('');
    this.fileResult.set(null);
    this.result.set(null);

    this.apiService.classifyFile(file).subscribe({
      next: (response) => {
        this.fileResult.set(response);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.error.set(err.error?.detail || 'An error occurred processing the file.');
        this.isLoading.set(false);
      },
    });
  }

  /** Clear the form */
  reset(): void {
    this.feedbackText.set('');
    this.result.set(null);
    this.selectedFile.set(null);
    this.fileResult.set(null);
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
      '.pdf': '📄',
      '.txt': '📝',
      '.docx': '📃',
      '.jpg': '🖼️',
      '.jpeg': '🖼️',
      '.png': '🖼️',
    };
    return icons[ext] || '📎';
  }
}
