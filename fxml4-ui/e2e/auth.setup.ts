/**
 * Authentication Setup for E2E Tests
 *
 * Handles different user authentication scenarios for comprehensive testing
 */

import { test as setup, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

// Test user configurations
const users = {
  standard: {
    email: process.env.E2E_TEST_EMAIL || 'test@fxml4.com',
    password: process.env.E2E_TEST_PASSWORD || 'test123',
    storageState: 'e2e/.auth/user.json',
  },
  admin: {
    email: process.env.E2E_ADMIN_EMAIL || 'admin@fxml4.com',
    password: process.env.E2E_ADMIN_PASSWORD || 'admin123',
    storageState: 'e2e/.auth/admin.json',
  },
  demo: {
    email: 'demo@fxml4.com',
    password: 'demo123',
    storageState: 'e2e/.auth/demo.json',
  },
};

// Ensure auth directory exists
const authDir = path.join(process.cwd(), 'e2e', '.auth');
if (!fs.existsSync(authDir)) {
  fs.mkdirSync(authDir, { recursive: true });
}

/**
 * Standard User Authentication
 */
setup('authenticate as standard user', async ({ page }) => {
  console.log('🔐 Setting up standard user authentication...');

  await performLogin(page, users.standard);

  // Verify standard user permissions
  await page.goto('/dashboard');
  await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

  // Verify standard user cannot access admin features
  await page.goto('/admin');
  await expect(page.locator('[data-testid="access-denied"]')).toBeVisible({ timeout: 5000 });

  // Save authentication state
  await page.context().storageState({ path: users.standard.storageState });
  console.log('✅ Standard user authentication setup complete');
});

/**
 * Admin User Authentication
 */
setup('authenticate as admin user', async ({ page }) => {
  console.log('🔐 Setting up admin user authentication...');

  await performLogin(page, users.admin);

  // Verify admin permissions
  await page.goto('/dashboard');
  await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

  // Verify admin can access admin features
  await page.goto('/admin');
  await expect(page.locator('[data-testid="admin-panel"]')).toBeVisible({ timeout: 10000 });

  // Save authentication state
  await page.context().storageState({ path: users.admin.storageState });
  console.log('✅ Admin user authentication setup complete');
});

/**
 * Demo User Authentication
 */
setup('authenticate as demo user', async ({ page }) => {
  console.log('🔐 Setting up demo user authentication...');

  await performLogin(page, users.demo);

  // Verify demo user has limited permissions
  await page.goto('/dashboard');
  await expect(page.locator('[data-testid="dashboard-container"]')).toBeVisible();

  // Verify demo user has trading restrictions
  await page.goto('/trading');
  await expect(page.locator('[data-testid="demo-mode-banner"]')).toBeVisible();

  // Save authentication state
  await page.context().storageState({ path: users.demo.storageState });
  console.log('✅ Demo user authentication setup complete');
});

/**
 * Perform login with given credentials
 */
async function performLogin(page: any, user: any) {
  try {
    // Navigate to login page
    await page.goto('/auth/login');

    // Wait for login form to be ready
    await page.waitForSelector('[data-testid="login-form"]', { timeout: 10000 });

    // Clear any existing values and fill credentials
    await page.fill('[data-testid="email-input"]', '');
    await page.fill('[data-testid="password-input"]', '');

    await page.fill('[data-testid="email-input"]', user.email);
    await page.fill('[data-testid="password-input"]', user.password);

    // Submit login form
    await page.click('[data-testid="login-button"]');

    // Wait for successful login redirect
    await page.waitForURL('**/dashboard', { timeout: 30000 });

    // Verify authentication success indicators
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible({ timeout: 10000 });

    // Wait for initial data load
    await page.waitForLoadState('networkidle');

    console.log(`✅ Login successful for ${user.email}`);

  } catch (error) {
    console.error(`❌ Login failed for ${user.email}:`, error);
    throw error;
  }
}

/**
 * Logout utility for tests
 */
export async function logout(page: any) {
  try {
    // Click user menu
    await page.click('[data-testid="user-menu"]');

    // Click logout option
    await page.click('[data-testid="logout-button"]');

    // Wait for redirect to login page
    await page.waitForURL('**/auth/login', { timeout: 10000 });

    console.log('✅ Logout successful');
  } catch (error) {
    console.error('❌ Logout failed:', error);
    throw error;
  }
}

/**
 * Switch user during test (re-authenticate)
 */
export async function switchUser(page: any, userType: keyof typeof users) {
  const user = users[userType];

  // Logout current user
  await logout(page);

  // Login as new user
  await performLogin(page, user);

  console.log(`✅ Switched to ${userType} user`);
}

/**
 * Verify authentication state
 */
export async function verifyAuthState(page: any, expectedUserType: string) {
  await page.goto('/profile');

  // Check user profile indicates correct user type
  const userRole = await page.locator('[data-testid="user-role"]').textContent();
  expect(userRole).toContain(expectedUserType);

  console.log(`✅ Verified user is ${expectedUserType}`);
}

export { users };
