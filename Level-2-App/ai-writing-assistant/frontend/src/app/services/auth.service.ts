import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../environments/environment';

export interface AuthResponse {
  id: string;
  email: string;
  fullName: string;
  token: string;
  refreshToken: string;
  expiresAt: string;
  message: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private gatewayUrl = environment.gatewayUrl;

  // Reactive state with signals
  private currentUserSignal = signal<AuthResponse | null>(this.loadUser());
  currentUser = this.currentUserSignal.asReadonly();
  isAuthenticated = computed(() => !!this.currentUserSignal());

  login(request: LoginRequest) {
    return this.http.post<AuthResponse>(`${this.gatewayUrl}/api/auth/login`, request);
  }

  register(request: RegisterRequest) {
    return this.http.post<AuthResponse>(`${this.gatewayUrl}/api/auth/register`, request);
  }

  googleLogin(code: string, redirectUri: string) {
    return this.http.post<AuthResponse>(`${this.gatewayUrl}/api/auth/google`, {
      code,
      redirectUri,
    });
  }

  githubLogin(code: string, clientId: string) {
    return this.http.post<AuthResponse>(`${this.gatewayUrl}/api/auth/github`, { code, clientId });
  }

  logout() {
    const refreshToken = this.currentUserSignal()?.refreshToken;
    this.http.post(`${this.gatewayUrl}/api/auth/logout`, { refreshToken }).subscribe();
    this.clearSession();
    this.router.navigate(['/login']);
  }

  setSession(response: AuthResponse) {
    this.currentUserSignal.set(response);
    localStorage.setItem('auth', JSON.stringify(response));
  }

  getToken(): string | null {
    return this.currentUserSignal()?.token ?? null;
  }

  private clearSession() {
    this.currentUserSignal.set(null);
    localStorage.removeItem('auth');
  }

  private loadUser(): AuthResponse | null {
    const stored = localStorage.getItem('auth');
    if (!stored) return null;
    const user = JSON.parse(stored) as AuthResponse;
    if (new Date(user.expiresAt) < new Date()) {
      localStorage.removeItem('auth');
      return null;
    }
    return user;
  }
}
