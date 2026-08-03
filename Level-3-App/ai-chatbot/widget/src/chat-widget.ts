import { LitElement, css, html, nothing } from 'lit'
import { customElement, property, state, query } from 'lit/decorators.js'
import { openSession, streamChat, type Source, type WidgetConfig } from './api'
import { parseSSE } from './sse'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  sources?: Source[]
}

const DEFAULT_PRIMARY = '#2563eb'

/**
 * `<chatbot-widget>` — the embeddable chat bubble + panel.
 *
 * Style-isolated via Shadow DOM. Lazily opens a widget session on first open
 * (the session response carries the safe public config), then streams each
 * chat turn over SSE. All message text is rendered as text nodes (never
 * innerHTML) so assistant/user content can't inject markup.
 */
@customElement('chatbot-widget')
export class ChatWidget extends LitElement {
  @property({ attribute: 'bot-id' }) botId = ''
  @property({ attribute: 'tenant-id' }) tenantId = ''
  @property({ attribute: 'api-base' }) apiBase = ''

  @state() private open = false
  @state() private loading = false
  @state() private sending = false
  @state() private error: string | null = null
  @state() private config: WidgetConfig | null = null
  @state() private messages: ChatMessage[] = []
  @state() private draft = ''

  private token: string | null = null
  private conversationId: string | null = null

  @query('.cb-scroll') private scrollEl?: HTMLElement

  static styles = css`
    :host {
      --cb-primary: #2563eb;
      --cb-radius: 16px;
      font-family:
        system-ui,
        -apple-system,
        'Segoe UI',
        Roboto,
        sans-serif;
      color: #1f2937;
    }

    button {
      font: inherit;
      cursor: pointer;
    }

    /* Launcher bubble — bottom-right, safe-area aware. */
    .cb-launcher {
      position: fixed;
      right: 16px;
      bottom: 16px;
      width: 56px;
      height: 56px;
      border: none;
      border-radius: 50%;
      background: var(--cb-primary);
      color: #fff;
      font-size: 24px;
      display: grid;
      place-items: center;
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25);
      z-index: 2147483000;
    }

    /* Panel — mobile-first: near-fullscreen bottom sheet. */
    .cb-panel {
      position: fixed;
      inset: 0;
      display: flex;
      flex-direction: column;
      background: #fff;
      z-index: 2147483001;
    }

    .cb-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 14px 16px;
      background: var(--cb-primary);
      color: #fff;
    }
    .cb-header strong {
      flex: 1;
      font-size: 1rem;
    }
    .cb-close {
      background: transparent;
      border: none;
      color: #fff;
      font-size: 22px;
      line-height: 1;
      padding: 4px;
    }

    .cb-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: #f9fafb;
    }

    .cb-msg {
      max-width: 85%;
      padding: 10px 12px;
      border-radius: var(--cb-radius);
      white-space: pre-wrap;
      word-wrap: break-word;
      line-height: 1.45;
      font-size: 0.95rem;
    }
    .cb-msg.user {
      align-self: flex-end;
      background: var(--cb-primary);
      color: #fff;
      border-bottom-right-radius: 4px;
    }
    .cb-msg.assistant {
      align-self: flex-start;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-bottom-left-radius: 4px;
    }
    .cb-cursor::after {
      content: '▋';
      margin-left: 2px;
      opacity: 0.5;
      animation: cb-blink 1s steps(2, start) infinite;
    }
    @keyframes cb-blink {
      to {
        visibility: hidden;
      }
    }

    .cb-sources {
      margin-top: 6px;
      font-size: 0.78rem;
      color: #6b7280;
    }
    .cb-sources summary {
      cursor: pointer;
    }
    .cb-sources ul {
      margin: 4px 0 0;
      padding-left: 16px;
    }

    .cb-suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }
    .cb-chip {
      border: 1px solid var(--cb-primary);
      color: var(--cb-primary);
      background: #fff;
      border-radius: 999px;
      padding: 6px 12px;
      font-size: 0.85rem;
    }

    .cb-composer {
      display: flex;
      gap: 8px;
      padding: 10px;
      border-top: 1px solid #e5e7eb;
      background: #fff;
    }
    .cb-composer textarea {
      flex: 1;
      resize: none;
      border: 1px solid #d1d5db;
      border-radius: 12px;
      padding: 10px 12px;
      font: inherit;
      max-height: 120px;
    }
    .cb-composer textarea:focus {
      outline: 2px solid var(--cb-primary);
      outline-offset: -1px;
    }
    .cb-send {
      border: none;
      border-radius: 12px;
      padding: 0 16px;
      background: var(--cb-primary);
      color: #fff;
      font-weight: 600;
    }
    .cb-send:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .cb-error {
      margin: 10px 16px 0;
      padding: 8px 12px;
      border-radius: 8px;
      background: #fef2f2;
      color: #b91c1c;
      font-size: 0.85rem;
    }

    /* Desktop: floating card instead of a fullscreen sheet. */
    @media (min-width: 480px) {
      .cb-panel {
        inset: auto;
        right: 20px;
        bottom: 20px;
        width: 380px;
        height: 560px;
        max-height: calc(100vh - 40px);
        border-radius: var(--cb-radius);
        overflow: hidden;
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
      }
    }
  `

  render() {
    return this.open ? this.renderPanel() : this.renderLauncher()
  }

  private renderLauncher() {
    return html` <button class="cb-launcher" aria-label="Open chat" @click=${this.toggleOpen}>💬</button> `
  }

  private renderPanel() {
    const title = this.config?.name ?? 'Assistant'
    return html`
      <section class="cb-panel" role="dialog" aria-label=${title}>
        <header class="cb-header">
          <strong>${title}</strong>
          <button class="cb-close" aria-label="Close chat" @click=${this.toggleOpen}>×</button>
        </header>

        ${this.error ? html`<div class="cb-error">${this.error}</div>` : nothing}

        <div class="cb-scroll">
          ${this.loading ? html`<div class="cb-msg assistant">…</div>` : nothing} ${this.renderWelcome()}
          ${this.messages.map((m) => this.renderMessage(m))}
        </div>

        <div class="cb-composer">
          <textarea
            rows="1"
            placeholder="Type a message…"
            .value=${this.draft}
            ?disabled=${this.sending || this.loading}
            @input=${this.onInput}
            @keydown=${this.onKeydown}></textarea>
          <button class="cb-send" ?disabled=${this.sending || this.loading || !this.draft.trim()} @click=${this.onSend}>Send</button>
        </div>
      </section>
    `
  }

  private renderWelcome() {
    if (this.messages.length > 0 || !this.config) {
      return nothing
    }
    const suggestions = this.config.suggested_questions ?? []
    return html`
      <div class="cb-msg assistant">
        ${this.config.welcome_message}
        ${suggestions.length
          ? html`
              <div class="cb-suggestions">
                ${suggestions.map((q) => html` <button class="cb-chip" @click=${() => this.send(q)}>${q}</button> `)}
              </div>
            `
          : nothing}
      </div>
    `
  }

  private renderMessage(m: ChatMessage) {
    return html` <div class="cb-msg ${m.role} ${m.streaming ? 'cb-cursor' : ''}">${m.content}${this.renderSources(m)}</div> `
  }

  private renderSources(m: ChatMessage) {
    if (m.role !== 'assistant' || !m.sources?.length) {
      return nothing
    }
    const unique = [...new Set(m.sources.map((s) => s.file_name))]
    return html`
      <details class="cb-sources">
        <summary>Sources (${unique.length})</summary>
        <ul>
          ${unique.map((name) => html`<li>${name}</li>`)}
        </ul>
      </details>
    `
  }

  private toggleOpen = () => {
    this.open = !this.open
    if (this.open && !this.token) {
      void this.ensureSession()
    }
  }

  private onInput = (e: Event) => {
    this.draft = (e.target as HTMLTextAreaElement).value
  }

  private onKeydown = (e: KeyboardEvent) => {
    // Enter sends; Shift+Enter inserts a newline.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      this.onSend()
    }
  }

  private onSend = () => {
    const text = this.draft.trim()
    if (text) {
      this.draft = ''
      void this.send(text)
    }
  }

  private base(): string {
    return this.apiBase || ''
  }

  private async ensureSession(): Promise<void> {
    if (this.token || this.loading) {
      return
    }
    if (!this.botId || !this.tenantId) {
      this.error = 'Widget is misconfigured (missing bot/tenant id).'
      return
    }
    this.loading = true
    this.error = null
    try {
      const session = await openSession(this.base(), this.botId, this.tenantId)
      this.token = session.access_token
      this.config = session.config
      this.style.setProperty('--cb-primary', session.config.primary_color || DEFAULT_PRIMARY)
    } catch {
      this.error = "Couldn't start the chat. Please try again later."
    } finally {
      this.loading = false
    }
  }

  private async send(text: string): Promise<void> {
    if (this.sending) {
      return
    }
    await this.ensureSession()
    if (!this.token) {
      return
    }

    this.error = null
    this.messages = [...this.messages, { role: 'user', content: text }]
    const assistant: ChatMessage = {
      role: 'assistant',
      content: '',
      streaming: true,
      sources: [],
    }
    this.messages = [...this.messages, assistant]
    this.sending = true

    try {
      const resp = await streamChat(this.base(), this.token, text, this.conversationId)
      for await (const ev of parseSSE(resp)) {
        this.applyEvent(ev.event, ev.data, assistant)
      }
    } catch {
      assistant.content ||= 'Sorry, something went wrong.'
    } finally {
      assistant.streaming = false
      this.sending = false
      this.messages = [...this.messages]
    }
  }

  private applyEvent(event: string, data: unknown, assistant: ChatMessage): void {
    const payload = (data ?? {}) as Record<string, unknown>
    switch (event) {
      case 'meta':
        this.conversationId = String(payload.conversation_id ?? '') || null
        break
      case 'sources':
        assistant.sources = Array.isArray(data) ? (data as Source[]) : []
        break
      case 'delta':
        assistant.content += String(payload.text ?? '')
        break
      case 'done':
        assistant.streaming = false
        break
      case 'error':
        assistant.content ||= String(payload.message ?? 'Something went wrong.')
        assistant.streaming = false
        break
      default:
        break
    }
    this.messages = [...this.messages]
  }

  protected updated(): void {
    // Keep the latest message in view as it streams in.
    if (this.scrollEl) {
      this.scrollEl.scrollTop = this.scrollEl.scrollHeight
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'chatbot-widget': ChatWidget
  }
}
