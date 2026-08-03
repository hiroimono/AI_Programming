// Dev demo bootstrap (served by `vite` via index.html). Reads the target
// bot/tenant from widget/.env (VITE_*) and mounts the widget on the host page.
// This mirrors what embed.ts does in production from <script> data-* attrs.

import { ChatWidget } from './chat-widget'

const botId = import.meta.env.VITE_BOT_ID as string | undefined
const tenantId = import.meta.env.VITE_TENANT_ID as string | undefined
const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8200'

if (!botId || !tenantId) {
  document.body.insertAdjacentHTML(
    'beforeend',
    '<p style="color:#b91c1c;padding:0 1rem">' +
      'Set VITE_BOT_ID and VITE_TENANT_ID in <code>widget/.env</code> ' +
      '(copy from .env.example) to mount the widget.' +
      '</p>',
  )
} else {
  const el = new ChatWidget()
  el.botId = botId
  el.tenantId = tenantId
  el.apiBase = apiBase
  document.body.appendChild(el)
}
