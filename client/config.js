/**
 * RefOnRecord Client — Environment Configuration
 *
 * Edit API_BASE to switch between the deployed server and a local instance.
 * This file is loaded before app.js so the constant is available globally.
 */
window.APP_CONFIG = {
  // Deployed via Vercel proxy (vercel.json rewrites /api/* to the VM)
  API_BASE: '',

  // Local development — uncomment the line below and comment out the one above
  // API_BASE: 'http://localhost:5000',
};
