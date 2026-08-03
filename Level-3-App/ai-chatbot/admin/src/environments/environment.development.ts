/**
 * Development environment.
 *
 * Points at the local FastAPI chatbot backend (dev port 8200). The backend
 * must allow this origin (http://localhost:4202) in its CORS_ORIGINS env.
 */
export const environment = {
  production: false,
  apiBase: 'http://localhost:8200',
};
