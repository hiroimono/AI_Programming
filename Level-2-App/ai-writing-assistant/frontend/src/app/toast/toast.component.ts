import { Component, signal } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

export interface ToastMessage {
  text: string;
  type: 'success' | 'info' | 'error';
}

@Component({
  selector: 'app-toast',
  imports: [MatIconModule],
  template: `
    @if (visible()) {
      <div class="toast" [class]="'toast-' + message().type" (click)="dismiss()">
        <mat-icon>{{ iconMap[message().type] }}</mat-icon>
        <span>{{ message().text }}</span>
      </div>
    }
  `,
  styles: `
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 20px;
      border-radius: 12px;
      font-size: 14px;
      color: #fff;
      cursor: pointer;
      z-index: 9999;
      animation: slideIn 0.3s ease-out;
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);

      mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }
    }

    .toast-success {
      background: rgba(34, 197, 94, 0.15);
      border-color: rgba(34, 197, 94, 0.3);
    }
    .toast-info {
      background: rgba(108, 99, 255, 0.15);
      border-color: rgba(108, 99, 255, 0.3);
    }
    .toast-error {
      background: rgba(239, 68, 68, 0.15);
      border-color: rgba(239, 68, 68, 0.3);
    }

    @keyframes slideIn {
      from {
        transform: translateX(100%);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
  `,
})
export class ToastComponent {
  visible = signal(false);
  message = signal<ToastMessage>({ text: '', type: 'info' });
  private timer: ReturnType<typeof setTimeout> | null = null;

  iconMap: Record<string, string> = {
    success: 'check_circle',
    info: 'info',
    error: 'error',
  };

  show(text: string, type: ToastMessage['type'] = 'info', duration = 4000) {
    if (this.timer) clearTimeout(this.timer);
    this.message.set({ text, type });
    this.visible.set(true);
    this.timer = setTimeout(() => this.dismiss(), duration);
  }

  dismiss() {
    this.visible.set(false);
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }
}
