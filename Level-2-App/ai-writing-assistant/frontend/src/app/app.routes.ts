import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';
import { guestGuard } from './guards/guest.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./chat/chat.component').then((m) => m.ChatComponent),
    canActivate: [authGuard],
  },
  {
    path: 'login',
    loadComponent: () => import('./auth/login.component').then((m) => m.LoginComponent),
    canActivate: [guestGuard],
  },
  {
    path: 'auth/google/callback',
    loadComponent: () =>
      import('./auth/google-callback.component').then((m) => m.GoogleCallbackComponent),
  },
  {
    path: 'auth/github/callback',
    loadComponent: () =>
      import('./auth/github-callback.component').then((m) => m.GitHubCallbackComponent),
  },
  { path: '**', redirectTo: '' },
];
