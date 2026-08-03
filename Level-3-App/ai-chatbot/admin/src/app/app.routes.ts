import { Routes } from '@angular/router';

import { authGuard } from './guards/auth.guard';
import { guestGuard } from './guards/guest.guard';

/**
 * App routes.
 *
 * /login is public (guestGuard bounces authed admins away). Everything else
 * lives under the ShellComponent layout (toolbar + <router-outlet>) behind
 * authGuard. Route params bind to component inputs via withComponentInputBinding.
 */
export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./auth/login').then((m) => m.LoginComponent),
    canActivate: [guestGuard],
  },
  {
    path: '',
    loadComponent: () => import('./shell/shell').then((m) => m.ShellComponent),
    canActivate: [authGuard],
    children: [
      {
        path: '',
        loadComponent: () => import('./bots/bots-list').then((m) => m.BotsListComponent),
      },
      {
        path: 'bots/:botId',
        loadComponent: () => import('./bots/bot-detail').then((m) => m.BotDetailComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
