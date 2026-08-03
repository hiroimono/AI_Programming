import { Component, Input, OnInit, ViewChild, inject, signal } from '@angular/core';
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
 * Bot detail shell: header (name + status) plus a two-column workspace. The
 * left column tabs between Settings (config) and Knowledge (documents); the
 * right column hosts a Live preview that stays visible on every tab so the
 * admin sees config changes immediately. On narrow screens the columns stack
 * (config on top, preview below) so the preview is still always reachable.
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
  @ViewChild(BotPreviewComponent) private preview?: BotPreviewComponent;

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

  /**
   * Keep the header in sync after Settings saves, then re-mint the live preview
   * so the new config (welcome, suggestions, color, model) is reflected at once.
   */
  onSaved(bot: Bot): void {
    this.bot.set(bot);
    this.preview?.reset();
  }
}
