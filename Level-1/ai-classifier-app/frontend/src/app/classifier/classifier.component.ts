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
import { ClassificationResponse } from '../models/classification.model';

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
  // Signal = modern equivalent of INotifyPropertyChanged in .NET
  // When value changes, template updates automatically.

  feedbackText = signal('');
  result = signal<ClassificationResponse | null>(null);
  isLoading = signal(false);
  error = signal('');

  // Computed = derived value dependent on other signals
  canSubmit = computed(() => this.feedbackText().trim().length >= 10 && !this.isLoading());

  // Confidence score as percentage
  confidencePercent = computed(() => {
    const r = this.result();
    return r ? Math.round(r.confidence * 100) : 0;
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

  /** Select a sample text and fill the textarea */
  useSample(text: string): void {
    this.feedbackText.set(text);
    this.result.set(null);
    this.error.set('');
  }

  /** Send AI classification request */
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

  /** Clear the form */
  reset(): void {
    this.feedbackText.set('');
    this.result.set(null);
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
  getConfidenceColor(): string {
    const pct = this.confidencePercent();
    if (pct >= 80) return '#22c55e';
    if (pct >= 50) return '#f59e0b';
    return '#ef4444';
  }
}
