import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { trigger, transition, style, animate, query, stagger } from '@angular/animations';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTabsModule } from '@angular/material/tabs';

import { AuthService } from '../services/auth.service';

/**
 * Public auth screen — same glassmorphism split-panel design as the Level-1
 * and Level-2 apps (animated gradient background, tab-switched Sign In /
 * Create Account panels, shake-on-error, password strength meter). No OAuth
 * here: the chatbot backend only supports email+password auth, and register
 * also creates the tenant (`tenant_name`). On success AuthService resolves
 * the admin+tenant identity and we route into the app.
 */
@Component({
  selector: 'app-login',
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatTabsModule,
  ],
  templateUrl: './login.html',
  styleUrl: './login.scss',
  animations: [
    trigger('fadeSlideIn', [
      transition(':enter', [
        query(
          '.form-field-animate',
          [
            style({ opacity: 0, transform: 'translateY(20px)' }),
            stagger(80, [
              animate(
                '400ms cubic-bezier(0.35, 0, 0.25, 1)',
                style({ opacity: 1, transform: 'translateY(0)' }),
              ),
            ]),
          ],
          { optional: true },
        ),
      ]),
    ]),
    trigger('shake', [
      transition('* => shake', [
        animate('400ms', style({ transform: 'translateX(-8px)' })),
        animate('100ms', style({ transform: 'translateX(8px)' })),
        animate('100ms', style({ transform: 'translateX(-4px)' })),
        animate('100ms', style({ transform: 'translateX(4px)' })),
        animate('100ms', style({ transform: 'translateX(0)' })),
      ]),
    ]),
  ],
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);

  readonly activeTab = signal(0);
  readonly submitting = signal(false);
  readonly error = signal<string | null>(null);
  readonly shakeState = signal('');

  showLoginPassword = false;
  showRegisterPassword = false;
  showConfirmPassword = false;

  readonly loginForm = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  readonly registerForm = this.fb.nonNullable.group({
    tenant_name: ['', [Validators.required]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    confirm_password: ['', [Validators.required]],
  });

  private readonly registerPasswordLive = toSignal(
    this.registerForm.controls.password.valueChanges,
    { initialValue: '' },
  );
  private readonly confirmPasswordLive = toSignal(
    this.registerForm.controls.confirm_password.valueChanges,
    { initialValue: '' },
  );

  readonly passwordStrength = computed(() => {
    const pw = this.registerPasswordLive();
    if (!pw) {
      return { score: 0, label: '', color: '' };
    }
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;

    const levels = [
      { label: '', color: '' },
      { label: 'Weak', color: '#ff6b6b' },
      { label: 'Fair', color: '#ffa94d' },
      { label: 'Strong', color: '#43e97b' },
      { label: 'Very Strong', color: '#6c63ff' },
      { label: 'Excellent', color: '#8b5cf6' },
    ];
    return { score, ...levels[score] };
  });

  readonly passwordsMatch = computed(() => {
    const confirm = this.confirmPasswordLive();
    return confirm ? this.registerPasswordLive() === confirm : true;
  });

  submitLogin(): void {
    if (this.loginForm.invalid || this.submitting()) {
      return;
    }
    this.error.set(null);
    this.submitting.set(true);
    this.auth.login(this.loginForm.getRawValue()).subscribe({
      next: () => this.router.navigate(['/']),
      error: (err) => this.fail(err, 'Sign in failed. Check your credentials.'),
    });
  }

  submitRegister(): void {
    if (this.registerForm.invalid || this.submitting() || !this.passwordsMatch()) {
      return;
    }
    this.error.set(null);
    this.submitting.set(true);
    const raw = this.registerForm.getRawValue();
    this.auth
      .register({ tenant_name: raw.tenant_name, email: raw.email, password: raw.password })
      .subscribe({
        next: () => this.router.navigate(['/']),
        error: (err) => this.fail(err, 'Registration failed. Please try again.'),
      });
  }

  private fail(err: unknown, fallback: string): void {
    this.submitting.set(false);
    const detail = (err as { error?: { detail?: unknown } })?.error?.detail;
    this.error.set(typeof detail === 'string' ? detail : fallback);
    this.shakeState.set('shake');
    setTimeout(() => this.shakeState.set(''), 500);
  }

  private errorMessage(err: unknown, fallback: string): string {
    const detail = (err as { error?: { detail?: unknown } })?.error?.detail;
    return typeof detail === 'string' ? detail : fallback;
  }
}
