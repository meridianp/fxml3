/**
 * Authentication E2E Tests
 *
 * Comprehensive testing of login, logout, registration, and authentication flows
 */

import { test, expect } from '@playwright/test';
import { logout, switchUser, verifyAuthState } from '../auth.setup';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Start each test from clean state
    await page.goto('/');
  });

  test('successful login with valid credentials', async ({ page }) => {
    await page.goto('/auth/login');

    // Wait for login form
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();

    // Fill credentials
    await page.fill('[data-testid="email-input"]', 'test@fxml4.com');
    await page.fill('[data-testid="password-input"]', 'test123');

    // Submit form
    await page.click('[data-testid="login-button"]');

    // Verify successful login
    await expect(page).toHaveURL(/.*\/dashboard/);
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
  });

  test('login failure with invalid credentials', async ({ page }) => {
    await page.goto('/auth/login');

    // Fill invalid credentials
    await page.fill('[data-testid="email-input"]', 'invalid@example.com');
    await page.fill('[data-testid="password-input"]', 'wrongpassword');

    // Submit form
    await page.click('[data-testid="login-button"]');

    // Verify error message
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-message"]')).toContainText('Invalid credentials');

    // Verify still on login page
    await expect(page).toHaveURL(/.*\/auth\/login/);
  });

  test('form validation for empty fields', async ({ page }) => {
    await page.goto('/auth/login');

    // Try to submit empty form
    await page.click('[data-testid="login-button"]');

    // Verify validation messages
    await expect(page.locator('[data-testid="email-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="password-error"]')).toBeVisible();
  });

  test('form validation for invalid email format', async ({ page }) => {
    await page.goto('/auth/login');

    // Fill invalid email
    await page.fill('[data-testid="email-input"]', 'invalid-email');
    await page.fill('[data-testid="password-input"]', 'password123');

    // Submit form
    await page.click('[data-testid="login-button"]');

    // Verify email validation error
    await expect(page.locator('[data-testid="email-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="email-error"]')).toContainText('Invalid email format');
  });

  test('remember me functionality', async ({ page }) => {
    await page.goto('/auth/login');

    // Fill credentials and check remember me
    await page.fill('[data-testid="email-input"]', 'test@fxml4.com');
    await page.fill('[data-testid="password-input"]', 'test123');
    await page.check('[data-testid="remember-me-checkbox"]');

    // Submit form
    await page.click('[data-testid="login-button"]');

    // Verify successful login
    await expect(page).toHaveURL(/.*\/dashboard/);

    // Close browser and reopen (simulate returning user)
    const context = page.context();
    await context.close();

    // TODO: Verify persistent login state
    // This would require testing with a fresh context
  });

  test('logout functionality', async ({ page }) => {
    // Login first
    await page.goto('/auth/login');
    await page.fill('[data-testid="email-input"]', 'test@fxml4.com');
    await page.fill('[data-testid="password-input"]', 'test123');
    await page.click('[data-testid="login-button"]');

    await expect(page).toHaveURL(/.*\/dashboard/);

    // Perform logout
    await logout(page);

    // Verify redirected to login
    await expect(page).toHaveURL(/.*\/auth\/login/);
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
  });

  test('registration flow', async ({ page }) => {
    await page.goto('/auth/register');

    // Wait for registration form
    await expect(page.locator('[data-testid="register-form"]')).toBeVisible();

    // Fill registration details
    const timestamp = Date.now();
    await page.fill('[data-testid="name-input"]', 'Test User');
    await page.fill('[data-testid="email-input"]', `test${timestamp}@fxml4.com`);
    await page.fill('[data-testid="password-input"]', 'password123');
    await page.fill('[data-testid="confirm-password-input"]', 'password123');

    // Accept terms
    await page.check('[data-testid="terms-checkbox"]');

    // Submit registration
    await page.click('[data-testid="register-button"]');

    // Verify successful registration (might redirect to email verification)
    await expect(page.locator('[data-testid="registration-success"]')).toBeVisible();
  });

  test('password reset flow', async ({ page }) => {
    await page.goto('/auth/login');

    // Click forgot password link
    await page.click('[data-testid="forgot-password-link"]');

    // Verify password reset form
    await expect(page.locator('[data-testid="reset-form"]')).toBeVisible();

    // Fill email
    await page.fill('[data-testid="reset-email-input"]', 'test@fxml4.com');

    // Submit reset request
    await page.click('[data-testid="reset-submit-button"]');

    // Verify success message
    await expect(page.locator('[data-testid="reset-success"]')).toBeVisible();
  });

  test('protected route access without authentication', async ({ page }) => {
    // Try to access protected route directly
    await page.goto('/dashboard');

    // Should redirect to login
    await expect(page).toHaveURL(/.*\/auth\/login/);

    // Verify redirect message
    await expect(page.locator('[data-testid="redirect-message"]')).toContainText('Please log in to continue');
  });

  test('navigation between auth pages', async ({ page }) => {
    await page.goto('/auth/login');

    // Navigate to registration
    await page.click('[data-testid="register-link"]');
    await expect(page).toHaveURL(/.*\/auth\/register/);
    await expect(page.locator('[data-testid="register-form"]')).toBeVisible();

    // Navigate back to login
    await page.click('[data-testid="login-link"]');
    await expect(page).toHaveURL(/.*\/auth\/login/);
    await expect(page.locator('[data-testid="login-form"]')).toBeVisible();
  });

  test('authentication persistence across page refreshes', async ({ page }) => {
    // Login
    await page.goto('/auth/login');
    await page.fill('[data-testid="email-input"]', 'test@fxml4.com');
    await page.fill('[data-testid="password-input"]', 'test123');
    await page.click('[data-testid="login-button"]');

    await expect(page).toHaveURL(/.*\/dashboard/);

    // Refresh page
    await page.reload();

    // Verify still authenticated
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test('session timeout handling', async ({ page }) => {
    // Login
    await page.goto('/auth/login');
    await page.fill('[data-testid="email-input"]', 'test@fxml4.com');
    await page.fill('[data-testid="password-input"]', 'test123');
    await page.click('[data-testid="login-button"]');

    await expect(page).toHaveURL(/.*\/dashboard/);

    // Simulate session timeout by clearing cookies
    await page.context().clearCookies();

    // Try to access protected content
    await page.goto('/trading');

    // Should redirect to login
    await expect(page).toHaveURL(/.*\/auth\/login/);
    await expect(page.locator('[data-testid="session-timeout-message"]')).toBeVisible();
  });
});
