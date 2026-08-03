/**
 * Auth-plane wire types (admin JWT).
 *
 * register/login return only a TokenResponse; identity (admin + tenant) comes
 * from a follow-up GET /api/auth/me. `StoredSession` is the merged shape we
 * persist client-side (localStorage) and expose via signals.
 */

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  tenant_name: string;
  email: string;
  password: string;
}

export interface Admin {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
}

export interface Tenant {
  id: string;
  name: string;
  plan: string;
}

export interface MeResponse {
  admin: Admin;
  tenant: Tenant;
}

/** What we keep in localStorage + the reactive session signal. */
export interface StoredSession {
  accessToken: string;
  /** ISO timestamp; computed from TokenResponse.expires_in at login time. */
  expiresAt: string;
  admin: Admin;
  tenant: Tenant;
}
