// API client + wire types for the chatbot backend (M4 widget + M5 chat).
// The widget only ever holds a scoped widget/preview token; it never sees
// admin credentials, system prompts, or model settings.

export interface WidgetConfig {
  bot_id: string;
  name: string;
  welcome_message: string;
  suggested_questions: string[];
  primary_color: string;
}

export interface SessionResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  session_id: string;
  config: WidgetConfig;
}

export interface Source {
  document_id: string;
  file_name: string;
  chunk_index: number;
  distance: number;
}

/** Open an anonymous widget session. The embed carries both ids; the backend
 * pins RLS to the claimed tenant and self-validates the (bot, tenant) pair. */
export async function openSession(
  apiBase: string,
  botId: string,
  tenantId: string,
): Promise<SessionResponse> {
  const resp = await fetch(`${apiBase}/api/widget/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_id: botId, tenant_id: tenantId }),
  });
  if (!resp.ok) {
    throw new Error(`session failed (${resp.status})`);
  }
  return (await resp.json()) as SessionResponse;
}

/** Start a chat turn. Returns the raw streaming Response so the caller can
 * consume Server-Sent Events off `response.body`. */
export async function streamChat(
  apiBase: string,
  token: string,
  message: string,
  conversationId: string | null,
): Promise<Response> {
  const resp = await fetch(`${apiBase}/api/widget/chat`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId ?? undefined,
    }),
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`chat failed (${resp.status})`);
  }
  return resp;
}
