import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, map, switchMap } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  LoginRequest,
  MeResponse,
  RegisterRequest,
  StoredSession,
  TokenResponse,
} from '../models/auth.model';

const STORAGE_KEY = 'chatbot_admin_session';

/**
 * Owns admin authentication state.
 *
 * Flow: login/register returns a bare JWT (TokenResponse); we immediately call
 * GET /api/auth/me with that token to resolve the admin + tenant identity, then
 * persist a merged StoredSession to localStorage and a reactive signal. The
 * token is attached to the /me call explicitly so there is no half-populated
 * session flash before identity is known.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private apiBase = environment.apiBase;

  private sessionSignal = signal<StoredSession | null>(this.loadSession());
  readonly session = this.sessionSignal.asReadonly();
  readonly isAuthenticated = computed(() => this.sessionSignal() !== null);
  readonly tenant = computed(() => this.sessionSignal()?.tenant ?? null);
  readonly admin = computed(() => this.sessionSignal()?.admin ?? null);

  login(request: LoginRequest): Observable<StoredSession> {
    return this.http
      .post<TokenResponse>(`${this.apiBase}/api/auth/login`, request)
      .pipe(switchMap((token) => this.completeAuth(token)));
  }

  register(request: RegisterRequest): Observable<StoredSession> {
    return this.http
      .post<TokenResponse>(`${this.apiBase}/api/auth/register`, request)
      .pipe(switchMap((token) => this.completeAuth(token)));
  }

  logout(): void {
    this.clearSession();
    this.router.navigate(['/login']);
  }

  /** Return a live token, or null if missing/expired (clears an expired one). */
  getToken(): string | null {
    const session = this.sessionSignal();
    if (!session) {
      return null;
    }
    if (new Date(session.expiresAt) <= new Date()) {
      this.clearSession();
      return null;
    }
    return session.accessToken;
  }

  private completeAuth(token: TokenResponse): Observable<StoredSession> {
    const expiresAt = new Date(Date.now() + token.expires_in * 1000).toISOString();
    // Attach the fresh token explicitly: the interceptor can't help yet because
    // no session is stored until /me succeeds.
    const headers = { Authorization: `Bearer ${token.access_token}` };
    return this.http.get<MeResponse>(`${this.apiBase}/api/auth/me`, { headers }).pipe(
      map((me) => {
        const session: StoredSession = {
          accessToken: token.access_token,
          expiresAt,
          admin: me.admin,
          tenant: me.tenant,
        };
        this.persist(session);
        return session;
      }),
    );
  }

  private persist(session: StoredSession): void {
    this.sessionSignal.set(session);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  }

  private clearSession(): void {
    this.sessionSignal.set(null);
    localStorage.removeItem(STORAGE_KEY);
  }

  private loadSession(): StoredSession | null {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    try {
      const parsed = JSON.parse(raw) as StoredSession;
      if (new Date(parsed.expiresAt) <= new Date()) {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }
      return parsed;
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
  }
}
