/**
 * Production environment.
 *
 * `apiBase` is the origin of the chatbot backend API.
 * The development build swaps this file for `environment.development.ts`
 * via angular.json fileReplacements.
 */
export const environment = {
  production: true,
  apiBase: 'https://aichatbot-production-b8f1.up.railway.app',
};
