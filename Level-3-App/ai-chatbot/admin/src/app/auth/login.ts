import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AuthService } from '../services/auth.service';
import { ToastService } from '../services/toast.service';

type AuthMode = 'login' | 'register';

/**
 * Public auth screen. Toggles between sign-in and self-service registration
 * (register also creates the tenant). On success the AuthService resolves the
 * admin+tenant identity and we route into the app.
 */
@Component({
  selector: 'app-login',
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatButtonToggleModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressBarModule,
  ],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);
  private toast = inject(ToastService);

  readonly mode = signal<AuthMode>('login');
  readonly submitting = signal(false);

  readonly loginForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  readonly registerForm = this.fb.nonNullable.group({
    tenant_name: ['', [Validators.required]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  setMode(mode: AuthMode): void {
    this.mode.set(mode);
  }

  submitLogin(): void {
    if (this.loginForm.invalid || this.submitting()) {
      return;
    }
    this.submitting.set(true);
    this.auth.login(this.loginForm.getRawValue()).subscribe({
      next: () => this.router.navigate(['/']),
      error: (err) => {
        this.submitting.set(false);
        this.toast.error(this.errorMessage(err, 'Sign in failed. Check your credentials.'));
      },
    });
  }

  submitRegister(): void {
    if (this.registerForm.invalid || this.submitting()) {
      return;
    }
    this.submitting.set(true);
    this.auth.register(this.registerForm.getRawValue()).subscribe({
      next: () => this.router.navigate(['/']),
      error: (err) => {
        this.submitting.set(false);
        this.toast.error(this.errorMessage(err, 'Registration failed.'));
      },
    });
  }

  private errorMessage(err: unknown, fallback: string): string {
    const detail = (err as { error?: { detail?: unknown } })?.error?.detail;
    return typeof detail === 'string' ? detail : fallback;
  }
}
