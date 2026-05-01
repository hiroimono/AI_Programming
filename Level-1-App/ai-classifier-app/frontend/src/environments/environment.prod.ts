// environment.prod.ts — Production configuration
// =================================================
// Used when building with `ng build --configuration production`.
// API_URL placeholder will be set during Cloudflare Pages build.
//
export const environment = {
  production: true,
  apiUrl: 'https://gateway-production-072b.up.railway.app/apps/classifier/api',
  gatewayUrl: 'https://gateway-production-072b.up.railway.app',
  googleClientId: '86560231507-0qf1loar8slgkv5qkbaa0bbl7lq47eq9.apps.googleusercontent.com',
  githubClientId: 'Ov23liDGqTlFdltnlbDw',
};
