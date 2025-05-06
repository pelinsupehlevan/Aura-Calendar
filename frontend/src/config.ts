// Configuration for the Aura Calendar app

// Environment settings
const isDevelopment = process.env.NODE_ENV !== 'production';

// Backend API settings
export const API_CONFIG = {
  // API base URL - in production, this would point to your deployed backend
  BASE_URL: isDevelopment ? 'http://localhost:8000' : 'https://api.auracalendar.com',
  
  // Default timeout in milliseconds
  TIMEOUT: 10000,
  
  // API version - for future use
  VERSION: 'v1',
};

// Feature flags
export const FEATURES = {
  // Enable/disable features
  ENABLE_NOTIFICATIONS: true,
  ENABLE_ANALYTICS: false,
};

export default {
  API_CONFIG,
  FEATURES,
};