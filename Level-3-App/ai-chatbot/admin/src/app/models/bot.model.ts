/**
 * Bot + BotConfig wire types. Mirrors the backend BotOut / BotConfigOut and
 * the partial update bodies (BotUpdate / BotConfigUpdate) — all fields on the
 * update types are optional (PATCH semantics, exclude_unset on the server).
 */

export type BotStatus = 'active' | 'disabled';

export interface BotConfig {
  id: string;
  welcome_message: string;
  system_prompt: string | null;
  model: string;
  temperature: number;
  suggested_questions: string[];
  primary_color: string;
}

export interface Bot {
  id: string;
  name: string;
  status: BotStatus;
  allowed_domains: string[];
  created_at: string;
  config?: BotConfig | null;
}

export interface BotCreate {
  name: string;
  allowed_domains: string[];
}

export interface BotUpdate {
  name?: string;
  status?: BotStatus;
  allowed_domains?: string[];
}

export interface BotConfigUpdate {
  welcome_message?: string;
  system_prompt?: string | null;
  model?: string;
  temperature?: number;
  suggested_questions?: string[];
  primary_color?: string;
}
