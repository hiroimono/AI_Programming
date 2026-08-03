import { Component, inject } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { AuthService } from '../services/auth.service';

/**
 * Authenticated layout shell: a top toolbar (brand, current tenant, logout)
 * plus a <router-outlet> for the bots list and bot detail child routes.
 */
@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, MatToolbarModule, MatButtonModule, MatIconModule],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class ShellComponent {
  private auth = inject(AuthService);
  readonly tenant = this.auth.tenant;

  logout(): void {
    this.auth.logout();
  }
}
