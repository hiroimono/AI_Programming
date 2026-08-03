import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { Bot, BotConfig, BotConfigUpdate, BotCreate, BotUpdate } from '../models/bot.model';
import { PreviewSessionResponse } from '../models/preview.model';

/**
 * Tenant-scoped bot + config API client.
 *
 * All calls are authenticated (Bearer added by authInterceptor); the backend
 * derives the tenant from the token and enforces RLS, so no tenant id is ever
 * sent from the client.
 */
@Injectable({ providedIn: 'root' })
export class BotService {
  private http = inject(HttpClient);
  private base = `${environment.apiBase}/api/bots`;

  list(): Observable<Bot[]> {
    return this.http.get<Bot[]>(this.base);
  }

  get(botId: string): Observable<Bot> {
    return this.http.get<Bot>(`${this.base}/${botId}`);
  }

  create(body: BotCreate): Observable<Bot> {
    return this.http.post<Bot>(this.base, body);
  }

  update(botId: string, body: BotUpdate): Observable<Bot> {
    return this.http.patch<Bot>(`${this.base}/${botId}`, body);
  }

  remove(botId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${botId}`);
  }

  getConfig(botId: string): Observable<BotConfig> {
    return this.http.get<BotConfig>(`${this.base}/${botId}/config`);
  }

  updateConfig(botId: string, body: BotConfigUpdate): Observable<BotConfig> {
    return this.http.patch<BotConfig>(`${this.base}/${botId}/config`, body);
  }

  openPreviewSession(botId: string): Observable<PreviewSessionResponse> {
    return this.http.post<PreviewSessionResponse>(`${this.base}/${botId}/preview-session`, {});
  }
}
