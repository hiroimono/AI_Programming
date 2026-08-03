import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { AuthService } from '../services/auth.service';

/**
 * Attach the admin Bearer token to API calls.
 *
 * Skipped for the public auth endpoints (login/register) which must not carry
 * a token. The /me call during login attaches its token explicitly, so this
 * interceptor is a no-op there too (no session stored yet).
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.getToken();
  const isAuthEndpoint =
    req.url.includes('/api/auth/login') || req.url.includes('/api/auth/register');

  if (token && !isAuthEndpoint) {
    return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
  }
  return next(req);
};
