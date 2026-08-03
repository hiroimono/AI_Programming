/**
 * Production environment.
 *
 * `apiBase` is the origin of the chatbot backend API. It is intentionally
 * empty here (same-origin / reverse-proxy assumption) and will be set to the
 * deployed backend URL during M8 (deploy step). The development build swaps
 * this file for `environment.development.ts` via angular.json fileReplacements.
 */
export const environment = {
  production: true,
  apiBase: '',
};
