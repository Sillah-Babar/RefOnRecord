/**
 * RefOnRecord Client — Environment Configuration
 *
 * Edit API_BASE to switch between the deployed server and a local instance.
 * This file is loaded before app.js so the constant is available globally.
 */
window.APP_CONFIG = {
  // Deployed on Vercel — requests go to /api/* which the serverless
  // function in api/[...path].js proxies to the VM over HTTP server-side
  API_BASE: '',

  // Local development — uncomment the line below and comment out the one above
  // API_BASE: 'http://localhost:5000',
};
