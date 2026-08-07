/**
 * Production environment.
 *
 * `apiBase` is the origin of the chatbot backend API (Railway deployment).
 * `widgetBase` is the origin serving the built widget.js (Cloudflare Pages).
 * The development build swaps this file for `environment.development.ts`
 * via angular.json fileReplacements.
 */
export const environment = {
  production: true,
  apiBase: 'https://aichatbot-production-b8f1.up.railway.app',
  widgetBase: 'https://ai-chatbot-widget-d9y.pages.dev',
};
