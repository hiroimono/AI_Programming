import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { Bot, BotCreate } from '../models/bot.model';
import { BotService } from '../services/bot.service';
import { ToastService } from '../services/toast.service';
import { CreateBotDialogComponent } from './create-bot-dialog';

/**
 * Landing page after login: lists the tenant's bots as cards. Supports create
 * (via dialog), delete (with confirm), and navigating into a bot's detail.
 */
@Component({
  selector: 'app-bots-list',
  imports: [
    DatePipe,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './bots-list.html',
  styleUrl: './bots-list.scss',
})
export class BotsListComponent {
  private botService = inject(BotService);
  private dialog = inject(MatDialog);
  private toast = inject(ToastService);
  private router = inject(Router);

  readonly bots = signal<Bot[]>([]);
  readonly loading = signal(true);

  constructor() {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.botService.list().subscribe({
      next: (bots) => {
        this.bots.set(bots);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.toast.error('Failed to load bots.');
      },
    });
  }

  openCreate(): void {
    const ref = this.dialog.open(CreateBotDialogComponent, { width: '420px' });
    ref.afterClosed().subscribe((body: BotCreate | undefined) => {
      if (!body) {
        return;
      }
      this.botService.create(body).subscribe({
        next: (bot) => {
          this.toast.success('Bot created.');
          this.router.navigate(['/bots', bot.id]);
        },
        error: () => this.toast.error('Could not create bot.'),
      });
    });
  }

  open(bot: Bot): void {
    this.router.navigate(['/bots', bot.id]);
  }

  confirmDelete(bot: Bot, event: Event): void {
    event.stopPropagation();
    const ok = window.confirm(
      `Delete bot "${bot.name}"? This removes its knowledge and cannot be undone.`,
    );
    if (!ok) {
      return;
    }
    this.botService.remove(bot.id).subscribe({
      next: () => {
        this.bots.update((list) => list.filter((b) => b.id !== bot.id));
        this.toast.success('Bot deleted.');
      },
      error: () => this.toast.error('Could not delete bot.'),
    });
  }
}
