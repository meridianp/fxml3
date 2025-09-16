/**
 * Authentication Service - Development Mock Implementation
 *
 * This provides temporary authentication to resolve 401 API errors
 * during development and testing phase.
 */

export interface AuthToken {
  token: string;
  expiresAt: number;
  userId: string;
}

export class AuthService {
  private static readonly DEV_TOKEN = 'dev-mock-token-fxml4-2025';
  private static readonly DEV_USER_ID = 'dev-user-001';
  private static currentAuth: AuthToken | null = {
    token: AuthService.DEV_TOKEN,
    expiresAt: Date.now() + (24 * 60 * 60 * 1000), // 24 hours
    userId: AuthService.DEV_USER_ID
  };

  /**
   * Get current authentication token
   */
  static getToken(): string | null {
    if (!this.currentAuth) return null;

    // Check if token is expired
    if (Date.now() > this.currentAuth.expiresAt) {
      this.currentAuth = null;
      return null;
    }

    return this.currentAuth.token;
  }

  /**
   * Get authentication headers for API requests
   */
  static getAuthHeaders(): Record<string, string> {
    const token = this.getToken();

    return {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };
  }

  /**
   * Check if user is authenticated
   */
  static isAuthenticated(): boolean {
    return this.getToken() !== null;
  }

  /**
   * Get current user ID
   */
  static getUserId(): string | null {
    return this.currentAuth?.userId || null;
  }

  /**
   * Mock login for development
   */
  static async mockLogin(): Promise<AuthToken> {
    const authToken: AuthToken = {
      token: this.DEV_TOKEN,
      expiresAt: Date.now() + (24 * 60 * 60 * 1000),
      userId: this.DEV_USER_ID
    };

    this.currentAuth = authToken;
    return authToken;
  }

  /**
   * Mock logout
   */
  static logout(): void {
    this.currentAuth = null;
  }

  /**
   * Refresh token (mock implementation)
   */
  static async refreshToken(): Promise<AuthToken | null> {
    if (!this.currentAuth) return null;

    // Mock refresh by extending expiration
    this.currentAuth.expiresAt = Date.now() + (24 * 60 * 60 * 1000);
    return this.currentAuth;
  }
}

export default AuthService;
