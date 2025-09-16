/**
 * Unit Tests for AuthService - JWT Authentication
 *
 * Red-Green-Refactor: Start with failing tests for authentication features
 * - JWT token generation and validation
 * - User authentication and authorization
 * - Session management and refresh tokens
 * - Role-based access control for trading operations
 */

import { AuthService, AuthResult, UserCredentials, JWTTokens } from '../../src/services/AuthService';

// Mock crypto and jwt libraries
jest.mock('jsonwebtoken', () => ({
  sign: jest.fn(() => 'mocked_jwt_token'),
  verify: jest.fn(),
  TokenExpiredError: class extends Error {}
}));

jest.mock('bcryptjs', () => ({
  hash: jest.fn(() => Promise.resolve('hashed_password_12345678901234567890123456789012345678901234567890')),
  compare: jest.fn()
}));

import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';

const mockJwt = jwt as jest.Mocked<typeof jwt>;
const mockBcrypt = bcrypt as jest.Mocked<typeof bcrypt>;

describe('AuthService - JWT Authentication', () => {
  let authService: AuthService;

  beforeEach(async () => {
    // Setup default mocks
    mockJwt.verify.mockReturnValue({ userId: 'user123', username: 'test@user.com', permissions: ['trade'] });
    mockBcrypt.compare.mockResolvedValue(true);

    authService = new AuthService({
      jwtSecret: 'test_secret_key_for_jwt_signing', // pragma: allowlist secret
      tokenExpiry: '1h',
      refreshTokenExpiry: '7d',
      bcryptRounds: 10
    });

    // Wait for initialization to complete
    await new Promise(resolve => setTimeout(resolve, 50));
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('User Authentication', () => {
    test('authenticates valid user credentials', async () => {
      const credentials: UserCredentials = {
        username: 'trader@fxml4.com',
        password: 'SecurePassword123!'  // pragma: allowlist secret
      };

      const result = await authService.login(credentials);

      expect(result.success).toBe(true);
      expect(result.tokens).toBeDefined();
      expect(result.tokens?.accessToken).toBeDefined();
      expect(result.tokens?.refreshToken).toBeDefined();
      expect(result.user).toBeDefined();
      expect(result.user?.username).toBe(credentials.username);
    });

    test('rejects invalid credentials', async () => {
      const credentials: UserCredentials = {
        username: 'invalid@user.com',
        password: 'wrongpassword'  // pragma: allowlist secret
      };

      const result = await authService.login(credentials);

      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
      expect(result.error?.code).toBe('INVALID_CREDENTIALS');
      expect(result.tokens).toBeUndefined();
    });

    test('handles empty credentials', async () => {
      const credentials: UserCredentials = {
        username: '',
        password: ''  // pragma: allowlist secret
      };

      const result = await authService.login(credentials);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('INVALID_INPUT');
    });
  });

  describe('JWT Token Management', () => {
    test('generates valid JWT tokens', async () => {
      const user = {
        id: 'user123',
        username: 'trader@fxml4.com',
        role: 'trader',
        permissions: ['trade', 'view_positions', 'view_market_data']
      };

      const tokens = await authService.generateTokens(user);

      expect(tokens.accessToken).toBeDefined();
      expect(tokens.refreshToken).toBeDefined();
      expect(typeof tokens.accessToken).toBe('string');
      expect(typeof tokens.refreshToken).toBe('string');
    });

    test('validates JWT access tokens', async () => {
      const validToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';

      const result = await authService.validateToken(validToken);

      expect(result.valid).toBe(true);
      expect(result.payload).toBeDefined();
      expect(result.payload?.userId).toBeDefined();
    });

    test('rejects invalid JWT tokens', async () => {
      // Mock JWT verify to throw error for invalid tokens
      mockJwt.verify.mockImplementationOnce(() => {
        throw new Error('Invalid token');
      });

      const invalidToken = 'invalid.jwt.token';

      const result = await authService.validateToken(invalidToken);

      expect(result.valid).toBe(false);
      expect(result.error).toBeDefined();
      expect(result.error?.code).toBe('INVALID_TOKEN');
    });

    test('rejects expired JWT tokens', async () => {
      // Mock JWT verify to throw TokenExpiredError
      mockJwt.verify.mockImplementationOnce(() => {
        throw new mockJwt.TokenExpiredError('Token expired');
      });

      const expiredToken = 'expired.jwt.token.signature';

      const result = await authService.validateToken(expiredToken);

      expect(result.valid).toBe(false);
      expect(result.error?.code).toBe('TOKEN_EXPIRED');
    });
  });

  describe('Refresh Token Management', () => {
    test('refreshes valid tokens', async () => {
      // First generate a refresh token through login
      const credentials: UserCredentials = {
        username: 'trader@fxml4.com',
        password: 'SecurePassword123!'  // pragma: allowlist secret
      };

      const loginResult = await authService.login(credentials);
      expect(loginResult.success).toBe(true);

      const refreshToken = loginResult.tokens!.refreshToken;

      // Mock JWT verify for refresh token
      mockJwt.verify.mockReturnValueOnce({ userId: 'trader-1', type: 'refresh' });

      const result = await authService.refreshTokens(refreshToken);

      expect(result.success).toBe(true);
      expect(result.tokens).toBeDefined();
      expect(result.tokens?.accessToken).toBeDefined();
      expect(result.tokens?.refreshToken).toBeDefined();
    });

    test('rejects invalid refresh tokens', async () => {
      const invalidRefreshToken = 'invalid_refresh_token';

      const result = await authService.refreshTokens(invalidRefreshToken);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('INVALID_REFRESH_TOKEN');
    });
  });

  describe('User Registration', () => {
    test('registers new user with valid data', async () => {
      const userData = {
        username: 'newtrader@fxml4.com',
        password: 'StrongPassword123!'  // pragma: allowlist secret,
        email: 'newtrader@fxml4.com',
        role: 'trader'
      };

      const result = await authService.register(userData);

      expect(result.success).toBe(true);
      expect(result.user).toBeDefined();
      expect(result.user?.username).toBe(userData.username);
      expect(result.tokens).toBeDefined();
    });

    test('rejects weak passwords', async () => {
      const userData = {
        username: 'weakpassuser@fxml4.com',
        password: '123'  // pragma: allowlist secret,
        email: 'weakpassuser@fxml4.com',
        role: 'trader'
      };

      const result = await authService.register(userData);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('WEAK_PASSWORD');
    });

    test('prevents duplicate user registration', async () => {
      // Try to register a user that already exists (trader@fxml4.com is pre-existing)
      const userData = {
        username: 'trader@fxml4.com', // This user already exists from initialization
        password: 'ValidPassword123!'  // pragma: allowlist secret,
        email: 'trader@fxml4.com',
        role: 'trader' as const
      };

      const result = await authService.register(userData);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('USER_EXISTS');
    });
  });

  describe('Role-Based Access Control', () => {
    test('validates trading permissions', async () => {
      // Mock JWT verify to return trader user payload with permissions
      mockJwt.verify.mockReturnValueOnce({
        userId: 'trader-1',
        username: 'trader@fxml4.com',
        permissions: ['trade', 'view_positions', 'view_market_data']
      });

      const userToken = 'valid_trader_token';

      const hasPermission = await authService.checkPermission(userToken, 'trade');

      expect(hasPermission).toBe(true);
    });

    test('denies admin permissions to regular traders', async () => {
      const traderToken = 'valid_trader_token';

      const hasPermission = await authService.checkPermission(traderToken, 'admin');

      expect(hasPermission).toBe(false);
    });

    test('validates admin permissions', async () => {
      // Mock JWT verify to return admin user payload
      mockJwt.verify.mockReturnValueOnce({
        userId: 'admin-1',
        username: 'admin@fxml4.com',
        permissions: ['admin', 'trade', 'view_positions', 'view_market_data', 'manage_users']
      });

      const adminToken = 'valid_admin_token';

      const hasPermission = await authService.checkPermission(adminToken, 'admin');

      expect(hasPermission).toBe(true);
    });
  });

  describe('Session Management', () => {
    test('logs out user and invalidates tokens', async () => {
      const accessToken = 'valid_access_token';

      const result = await authService.logout(accessToken);

      expect(result.success).toBe(true);
      expect(result.message).toBe('Successfully logged out');
    });

    test('gets current user from token', async () => {
      // Mock JWT verify to return trader user payload
      mockJwt.verify.mockReturnValueOnce({
        userId: 'trader-1',
        username: 'trader@fxml4.com',
        permissions: ['trade', 'view_positions', 'view_market_data']
      });

      const accessToken = 'valid_access_token';

      const result = await authService.getCurrentUser(accessToken);

      expect(result.success).toBe(true);
      expect(result.user).toBeDefined();
      expect(result.user?.username).toBeDefined();
    });

    test('handles invalid session token', async () => {
      // Mock JWT verify to throw error
      mockJwt.verify.mockImplementationOnce(() => {
        throw new Error('Invalid token');
      });

      const invalidToken = 'invalid_session_token';

      const result = await authService.getCurrentUser(invalidToken);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('INVALID_SESSION');
    });
  });

  describe('Security Features', () => {
    test('implements rate limiting for login attempts', async () => {
      const credentials: UserCredentials = {
        username: 'attacker@malicious.com',
        password: 'wrongpassword'  // pragma: allowlist secret
      };

      // Simulate multiple failed login attempts
      for (let i = 0; i < 5; i++) {
        await authService.login(credentials);
      }

      const result = await authService.login(credentials);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('RATE_LIMITED');
    });

    test('tracks login attempts and security events', async () => {
      const credentials: UserCredentials = {
        username: 'trader@fxml4.com', // Use existing user
        password: 'SecurePassword123!'  // pragma: allowlist secret
      };

      await authService.login(credentials);

      const securityLog = await authService.getSecurityLog('trader@fxml4.com');

      expect(securityLog.events).toBeDefined();
      expect(securityLog.events.length).toBeGreaterThan(0);
      expect(securityLog.events[0].type).toBe('LOGIN_SUCCESS');
    });
  });

  describe('Password Security', () => {
    test('hashes passwords securely', async () => {
      const plainPassword = 'MySecretPassword123!'; // pragma: allowlist secret

      const hashedPassword = await authService.hashPassword(plainPassword);

      expect(hashedPassword).toBeDefined();
      expect(hashedPassword).not.toBe(plainPassword);
      expect(hashedPassword.length).toBeGreaterThan(50);
    });

    test('verifies password against hash', async () => {
      const plainPassword = 'MySecretPassword123!'; // pragma: allowlist secret
      const hashedPassword = await authService.hashPassword(plainPassword);

      const isValid = await authService.verifyPassword(plainPassword, hashedPassword);

      expect(isValid).toBe(true);
    });

    test('rejects incorrect password verification', async () => {
      const plainPassword = 'MySecretPassword123!'; // pragma: allowlist secret
      const wrongPassword = 'WrongPassword456!';  // pragma: allowlist secret
      const hashedPassword = await authService.hashPassword(plainPassword);

      // Mock bcrypt.compare to return false for wrong password
      mockBcrypt.compare.mockResolvedValueOnce(false);

      const isValid = await authService.verifyPassword(wrongPassword, hashedPassword);

      expect(isValid).toBe(false);
    });
  });
});
