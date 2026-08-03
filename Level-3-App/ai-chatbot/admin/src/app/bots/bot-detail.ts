import { Component, Input, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTabsModule } from '@angular/material/tabs';

import { Bot } from '../models/bot.model';
import { BotService } from '../services/bot.service';
import { ToastService } from '../services/toast.service';
import { BotKnowledgeComponent } from './bot-knowledge';
import { BotPreviewComponent } from './bot-preview';
import { BotSettingsComponent } from './bot-settings';

/**
 * Bot detail shell: header (name + status) plus a three-tab workspace —
 * Settings (config), Knowledge (documents) and Preview (live test chat).
 * The Knowledge and Preview tabs are lazily rendered (matTabContent) so their
 * network work only happens when the admin actually opens them.
 * `botId` is bound from the route param via withComponentInputBinding.
 */
@Component({
  selector: 'app-bot-detail',
  imports: [
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTabsModule,
    BotSettingsComponent,
    BotKnowledgeComponent,
    BotPreviewComponent,
  ],
  templateUrl: './bot-detail.html',
  styleUrl: './bot-detail.scss',
})
export class BotDetailComponent implements OnInit {
  @Input() botId = '';

  private botService = inject(BotService);
  private toast = inject(ToastService);

  readonly bot = signal<Bot | null>(null);
  readonly loading = signal(true);

  ngOnInit(): void {
    this.botService.get(this.botId).subscribe({
      next: (bot) => {
        this.bot.set(bot);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.toast.error('Failed to load bot.');
      },
    });
  }

  /** Keep the header in sync after Settings saves name/status changes. */
  onSaved(bot: Bot): void {
    this.bot.set(bot);
  }
}
