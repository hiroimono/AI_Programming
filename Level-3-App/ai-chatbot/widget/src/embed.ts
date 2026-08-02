// Production entry (IIFE build → dist/widget.js). A tenant embeds:
//   <script src=".../widget.js"
//           data-bot-id="…" data-tenant-id="…" data-api-base="https://api…">
//   </script>
// This script finds its own tag, reads the data-* attributes, and mounts one
// <chatbot-widget> onto the page.

import { ChatWidget } from "./chat-widget";

// Capture synchronously: document.currentScript is only valid while this
// script is first executing (before any await / DOMContentLoaded).
const self = document.currentScript as HTMLScriptElement | null;

function mount(): void {
  const script =
    self ?? document.querySelector<HTMLScriptElement>("script[data-bot-id]");
  if (!script) {
    return;
  }
  const botId = script.getAttribute("data-bot-id");
  const tenantId = script.getAttribute("data-tenant-id");
  const apiBase = script.getAttribute("data-api-base") ?? "";
  if (!botId || !tenantId) {
    // eslint-disable-next-line no-console
    console.error(
      "[chatbot-widget] data-bot-id and data-tenant-id are required",
    );
    return;
  }
  const el = new ChatWidget();
  el.botId = botId;
  el.tenantId = tenantId;
  el.apiBase = apiBase;
  document.body.appendChild(el);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount, { once: true });
} else {
  mount();
}
