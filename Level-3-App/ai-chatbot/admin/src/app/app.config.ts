import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding, withViewTransitions } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimations } from '@angular/platform-browser/animations';

import { routes } from './app.routes';
import { authInterceptor } from './interceptors/auth.interceptor';

/**
 * Root application providers.
 *
 * - withComponentInputBinding: lets route params (e.g. :botId) bind straight to
 *   component @Input()s without manually reading ActivatedRoute.
 * - authInterceptor: adds the admin Bearer token to API requests.
 * - provideAnimations: required by Angular Material overlays (dialog, snackbar).
 */
export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withViewTransitions(), withComponentInputBinding()),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAnimations(),
  ],
};
