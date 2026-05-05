import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-google-callback',
  template: `
    <div class="callback-container">
      <div class="callback-card">
        @if (error) {
          <p class="error">{{ error }}</p>
          <a routerLink="/login">Back to Login</a>
        } @else {
          <p>Authenticating with Google...</p>
        }
      </div>
    </div>
  `,
  styles: `
    .callback-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: #0f0f1a;
    }
    .callback-card {
      color: #e2e8f0;
      text-align: center;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .error {
      color: #ff6b6b;
    }
    a {
      color: #6c63ff;
    }
  `,
})
export class GoogleCallbackComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private auth = inject(AuthService);

  error = '';

  ngOnInit() {
    const code = this.route.snapshot.queryParamMap.get('code');
    const returnedState = this.route.snapshot.queryParamMap.get('state');

    if (!code) {
      this.error = 'No authorization code received from Google.';
      return;
    }

    // Verify OAuth state to prevent CSRF attacks
    const savedState = sessionStorage.getItem('oauth_state_google');
    sessionStorage.removeItem('oauth_state_google');

    if (!savedState || savedState !== returnedState) {
      this.error = 'Invalid OAuth state. Please try logging in again.';
      return;
    }

    const redirectUri = `${window.location.origin}/auth/google/callback`;

    this.auth.googleLogin(code, redirectUri).subscribe({
      next: (response) => {
        this.auth.setSession(response);
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.error = err.error?.message ?? 'Google authentication failed.';
      },
    });
  }
}
