import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { BotCreate } from '../models/bot.model';

/**
 * Dialog to create a bot. `allowed_domains` is entered as a comma-separated
 * list and normalized to a string[] on save. Closes with a BotCreate payload,
 * or undefined on cancel.
 */
@Component({
  selector: 'app-create-bot-dialog',
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  template: `
    <h2 mat-dialog-title>New bot</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="dialog-form">
        <mat-form-field appearance="outline" class="full">
          <mat-label>Bot name</mat-label>
          <input matInput formControlName="name" placeholder="Support assistant" />
        </mat-form-field>
        <mat-form-field appearance="outline" class="full">
          <mat-label>Allowed domains</mat-label>
          <input
            matInput
            formControlName="allowed_domains"
            placeholder="example.com, app.example.com"
          />
          <mat-hint>Comma-separated. Leave empty to decide later.</mat-hint>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="cancel()">Cancel</button>
      <button mat-flat-button (click)="save()" [disabled]="form.invalid">Create</button>
    </mat-dialog-actions>
  `,
  styles: `
    .dialog-form {
      display: flex;
      flex-direction: column;
      padding-top: 8px;
    }
    .full {
      width: 100%;
    }
  `,
})
export class CreateBotDialogComponent {
  private fb = inject(FormBuilder);
  private dialogRef = inject(MatDialogRef<CreateBotDialogComponent, BotCreate>);

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    allowed_domains: [''],
  });

  cancel(): void {
    this.dialogRef.close();
  }

  save(): void {
    if (this.form.invalid) {
      return;
    }
    const raw = this.form.getRawValue();
    const domains = raw.allowed_domains
      .split(',')
      .map((d) => d.trim())
      .filter((d) => d.length > 0);
    this.dialogRef.close({ name: raw.name.trim(), allowed_domains: domains });
  }
}
