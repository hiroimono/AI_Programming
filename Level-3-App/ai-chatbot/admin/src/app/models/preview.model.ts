/**
 * Preview + chat wire types.
 *
 * The admin panel previews a bot by minting a short-lived PREVIEW token
 * (POST /api/bots/:id/preview-session, admin-authenticated) and then streaming
 * chat turns over POST /api/widget/chat with that token. These shapes mirror
 * the widget's own types so the preview chat behaves exactly like production.
 */

export interface WidgetConfig {
  bot_id: string;
  name: string;
  welcome_message: string;
  suggested_questions: string[];
  primary_color: string;
}

export interface PreviewSessionResponse {
  access_token: string;
  token_type?: string;
  expires_in: number;
  session_id: string;
  config: WidgetConfig;
}

/** One retrieval hit surfaced under an assistant answer. */
export interface ChatSource {
  document_id: string;
  file_name: string;
  chunk_index: number;
  distance: number;
}

/** A single message rendered in the preview thread. */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  streaming?: boolean;
  sources?: ChatSource[];
}
