// Auto-authentication utility - gets JWT token automatically without user login
const API_BASE_URL = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

let cachedToken: string | null = null;

export const authService = {
  // Automatically get JWT token using default credentials
  async getToken(): Promise<string> {
    // Return cached token if available
    if (cachedToken) {
      return cachedToken;
    }

    // Check localStorage first
    const stored = localStorage.getItem('jwt_token');
    if (stored) {
      cachedToken = stored;
      return stored;
    }

    // Auto-login with default credentials
    try {
      const response = await fetch(`${API_BASE_URL}/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: 'admin',
          password: 'highwire123',
        }),
      });

      if (response.ok) {
        const data = await response.json();
        cachedToken = data.access_token;
        localStorage.setItem('jwt_token', data.access_token);
        return data.access_token;
      }
    } catch (error) {
      console.error('Auto-authentication failed:', error);
    }

    return '';
  },

  // Get authorization header with auto-authentication
  async getAuthHeader(): Promise<Record<string, string>> {
    const token = await this.getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  },

  // Clear token (for token refresh on 401)
  clearToken(): void {
    cachedToken = null;
    localStorage.removeItem('jwt_token');
  },
};
