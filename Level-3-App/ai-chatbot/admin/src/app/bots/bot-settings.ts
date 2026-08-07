import { Component, EventEmitter, Input, OnInit, Output, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatSliderModule } from '@angular/material/slider';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { forkJoin } from 'rxjs';

import { environment } from '../../environments/environment';
import { Bot, BotConfigUpdate, BotUpdate } from '../models/bot.model';
import { AuthService } from '../services/auth.service';
import { BotService } from '../services/bot.service';
import { ToastService } from '../services/toast.service';

/** Chat models the admin can pick for a bot. */
const MODEL_OPTIONS = ['gpt-4o-mini', 'gpt-4o'] as const;

/**
 * Settings tab: edits bot identity (name, status, allowed domains) and its
 * BotConfig (welcome message, system prompt, model, temperature, suggested
 * questions, primary color) in one form. Saving issues both PATCHes together
 * (forkJoin) and emits the merged bot so the parent header stays in sync.
 * Also renders a copy-paste embed snippet for the widget.
 */
@Component({
  selector: 'app-bot-settings',
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    MatSliderModule,
    MatSlideToggleModule,
  ],
  templateUrl: './bot-settings.html',
  styleUrl: './bot-settings.scss',
})
export class BotSettingsComponent implements OnInit {
  @Input({ required: true }) bot!: Bot;
  @Output() saved = new EventEmitter<Bot>();

  private fb = inject(FormBuilder);
  private botService = inject(BotService);
  private auth = inject(AuthService);
  private toast = inject(ToastService);

  readonly modelOptions = MODEL_OPTIONS;
  readonly saving = signal(false);

  form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    active: [true],
    allowed_domains: [''],
    welcome_message: [''],
    system_prompt: [''],
    model: ['gpt-4o-mini'],
    temperature: [0.3],
    suggested_questions: [''],
    primary_color: ['#2563eb'],
  });

  ngOnInit(): void {
    const config = this.bot.config ?? null;
    this.form.setValue({
      name: this.bot.name,
      active: this.bot.status === 'active',
      allowed_domains: this.bot.allowed_domains.join(', '),
      welcome_message: config?.welcome_message ?? '',
      system_prompt: config?.system_prompt ?? '',
      model: config?.model ?? 'gpt-4o-mini',
      temperature: config?.temperature ?? 0.3,
      suggested_questions: (config?.suggested_questions ?? []).join('\n'),
      primary_color: config?.primary_color ?? '#2563eb',
    });
  }

  save(): void {
    if (this.form.invalid || this.saving()) {
      return;
    }
    this.saving.set(true);
    const raw = this.form.getRawValue();

    const botUpdate: BotUpdate = {
      name: raw.name.trim(),
      status: raw.active ? 'active' : 'disabled',
      allowed_domains: this.splitCsv(raw.allowed_domains),
    };
    const configUpdate: BotConfigUpdate = {
      welcome_message: raw.welcome_message,
      system_prompt: raw.system_prompt.trim() ? raw.system_prompt : null,
      model: raw.model,
      temperature: raw.temperature,
      suggested_questions: this.splitLines(raw.suggested_questions),
      primary_color: raw.primary_color,
    };

    forkJoin({
      bot: this.botService.update(this.bot.id, botUpdate),
      config: this.botService.updateConfig(this.bot.id, configUpdate),
    }).subscribe({
      next: ({ bot, config }) => {
        this.saving.set(false);
        this.saved.emit({ ...bot, config });
        this.toast.success('Settings saved.');
      },
      error: () => {
        this.saving.set(false);
        this.toast.error('Could not save settings.');
      },
    });
  }

  embedSnippet(): string {
    const apiBase = environment.apiBase || 'https://your-api-host';
    const widgetBase = environment.widgetBase || 'https://your-widget-host';
    const tenantId = this.auth.tenant()?.id ?? '';
    return [
      '<script',
      `  src="${widgetBase}/widget.js"`,
      `  data-bot-id="${this.bot.id}"`,
      `  data-tenant-id="${tenantId}"`,
      `  data-api-base="${apiBase}"`,
      '  defer></script>',
    ].join('\n');
  }

  copyEmbed(): void {
    navigator.clipboard.writeText(this.embedSnippet()).then(
      () => this.toast.success('Embed snippet copied.'),
      () => this.toast.error('Copy failed — select and copy manually.'),
    );
  }

  private splitCsv(value: string): string[] {
    return value
      .split(',')
      .map((v) => v.trim())
      .filter((v) => v.length > 0);
  }

  private splitLines(value: string): string[] {
    return value
      .split('\n')
      .map((v) => v.trim())
      .filter((v) => v.length > 0);
  }
}
