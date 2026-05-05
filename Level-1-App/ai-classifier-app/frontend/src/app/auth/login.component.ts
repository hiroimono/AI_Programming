import { Component, inject, signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { trigger, transition, style, animate, query, stagger } from '@angular/animations';
import { AuthService } from '../services/auth.service';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-login',
  imports: [
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatCheckboxModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
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
  private auth = inject(AuthService);
  private router = inject(Router);

  // Login state
  loginEmail = '';
  loginPassword = '';
  rememberMe = false;
  showLoginPassword = false;

  // Register state
  firstName = '';
  lastName = '';
  registerEmail = '';
  registerPassword = '';
  confirmPassword = '';
  agreeTerms = false;
  showRegisterPassword = false;
  showConfirmPassword = false;

  // UI state
  error = signal<string | null>(null);
  loading = signal(false);
  activeTab = signal(0);
  shakeState = signal('');

  // Password strength
  passwordStrength = computed(() => {
    const pw = this.registerPassword;
    if (!pw) return { score: 0, label: '', color: '' };
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;

    const levels = [
      { label: '', color: '' },
      { label: 'Weak', color: 'var(--error)' },
      { label: 'Fair', color: 'var(--warning)' },
      { label: 'Strong', color: '#43E97B' },
      { label: 'Very Strong', color: 'var(--accent-start)' },
      { label: 'Excellent', color: 'var(--accent-end)' },
    ];
    return { score, ...levels[score] };
  });

  passwordsMatch = computed(() =>
    this.registerPassword && this.confirmPassword
      ? this.registerPassword === this.confirmPassword
      : true,
  );

  onLogin() {
    this.error.set(null);
    this.loading.set(true);

    this.auth.login({ email: this.loginEmail, password: this.loginPassword }).subscribe({
      next: (response) => {
        this.auth.setSession(response);
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err.error?.message ?? 'Login failed. Please check your credentials.');
        this.shakeState.set('shake');
        setTimeout(() => this.shakeState.set(''), 500);
      },
    });
  }

  onRegister() {
    if (this.registerPassword !== this.confirmPassword) {
      this.error.set('Passwords do not match');
      return;
    }
    this.error.set(null);
    this.loading.set(true);

    this.auth
      .register({
        email: this.registerEmail,
        password: this.registerPassword,
        firstName: this.firstName,
        lastName: this.lastName,
      })
      .subscribe({
        next: (response) => {
          this.auth.setSession(response);
          this.router.navigate(['/']);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err.error?.message ?? 'Registration failed. Please try again.');
          this.shakeState.set('shake');
          setTimeout(() => this.shakeState.set(''), 500);
        },
      });
  }

  onGoogleLogin() {
    // Redirect to Google OAuth2 consent page (authorization code flow)
    const clientId = environment.googleClientId;
    const redirectUri = `${window.location.origin}/auth/google/callback`;
    const scope = 'openid email profile';
    const state = this.generateOAuthState('google');

    window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scope)}&access_type=offline&prompt=consent&state=${state}`;
  }

  onGithubLogin() {
    // Redirect to GitHub OAuth authorize page
    const clientId = environment.githubClientId;
    const redirectUri = `${window.location.origin}/auth/github/callback`;
    const scope = 'user:email';
    const state = this.generateOAuthState('github');

    window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${scope}&state=${state}`;
  }

  /**
   * Generates a cryptographically random state token for OAuth CSRF protection.
   * Stores it in sessionStorage so the callback component can verify it.
   */
  private generateOAuthState(provider: string): string {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    const state = Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('');
    sessionStorage.setItem(`oauth_state_${provider}`, state);
    return state;
  }
}
