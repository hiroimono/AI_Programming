import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { environment } from '../../environments/environment';

@Component({
  selector: 'app-github-callback',
  template: `
    <div class="callback-container">
      <div class="callback-card">
        @if (error) {
          <p class="error">{{ error }}</p>
          <a routerLink="/login">Back to Login</a>
        } @else {
          <p>Authenticating with GitHub...</p>
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
      background: #0d0d1a;
    }
    .callback-card {
      color: #e2e8f0;
      text-align: center;
      font-family: 'Inter', sans-serif;
    }
    .error {
      color: #ff6b6b;
    }
    a {
      color: #6c63ff;
    }
  `,
})
export class GitHubCallbackComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private auth = inject(AuthService);

  error = '';

  ngOnInit() {
    const code = this.route.snapshot.queryParamMap.get('code');
    const returnedState = this.route.snapshot.queryParamMap.get('state');

    if (!code) {
      this.error = 'No authorization code received from GitHub.';
      return;
    }

    const savedState = sessionStorage.getItem('oauth_state_github');
    sessionStorage.removeItem('oauth_state_github');

    if (!savedState || savedState !== returnedState) {
      this.error = 'Invalid OAuth state. Please try logging in again.';
      return;
    }

    this.auth.githubLogin(code, environment.githubClientId).subscribe({
      next: (response) => {
        this.auth.setSession(response);
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.error = err.error?.message ?? 'GitHub authentication failed.';
      },
    });
  }
}
