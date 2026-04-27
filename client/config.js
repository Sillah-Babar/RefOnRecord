/**
 * RefOnRecord Client — Environment Configuration
 *
 * Edit API_BASE to switch between the deployed server and a local instance.
 * This file is loaded before app.js so the constant is available globally.
 */
window.APP_CONFIG = {
  // Deployed server (default)
  API_BASE: 'http://74.241.132.64:8080',

  // Local development — uncomment the line below and comment out the one above
  // API_BASE: 'http://localhost:5000',
};
