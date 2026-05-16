import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';
import { guestGuard } from './guards/guest.guard';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./auth/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'auth/github/callback',
    loadComponent: () =>
      import('./auth/github-callback.component').then((m) => m.GitHubCallbackComponent),
  },
  {
    path: 'auth/google/callback',
    loadComponent: () =>
      import('./auth/google-callback.component').then((m) => m.GoogleCallbackComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./classifier/classifier.component').then((m) => m.ClassifierComponent),
  },
  {
    path: '**',
    redirectTo: '',
  },
];
