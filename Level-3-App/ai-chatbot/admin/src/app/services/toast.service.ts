import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

/**
 * Thin wrapper over MatSnackBar for consistent success/error toasts.
 */
@Injectable({ providedIn: 'root' })
export class ToastService {
  private snackBar = inject(MatSnackBar);

  success(message: string): void {
    this.snackBar.open(message, 'OK', {
      duration: 3000,
      panelClass: 'toast-success',
      horizontalPosition: 'center',
      verticalPosition: 'bottom',
    });
  }

  error(message: string): void {
    this.snackBar.open(message, 'Dismiss', {
      duration: 5000,
      panelClass: 'toast-error',
      horizontalPosition: 'center',
      verticalPosition: 'bottom',
    });
  }
}
