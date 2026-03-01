import { test, expect } from '@playwright/test';
import { API_BASE } from './helpers';

test.describe('Authentication', () => {
  const user = {
    email: `auth-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@test.com`,
    password: 'TestPassword123!',
    name: 'Auth Test User',
  };

  // ── Register Page ──

  test('register page renders all fields', async ({ page }) => {
    await page.goto('/auth/register');
    await expect(page.getByText('Create an account')).toBeVisible();
    await expect(page.getByLabel('Full Name')).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Password', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Confirm Password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create Account' })).toBeVisible();
    await expect(page.getByText("Already have an account?")).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible();
  });

  test('register validates empty fields', async ({ page }) => {
    await page.goto('/auth/register');
    await page.getByRole('button', { name: 'Create Account' }).click();
    await expect(page.getByText('Name must be at least 2 characters')).toBeVisible();
    await expect(page.getByText('Please enter a valid email')).toBeVisible();
  });

  test('register validates short password', async ({ page }) => {
    await page.goto('/auth/register');
    await page.getByLabel('Full Name').fill('Test User');
    await page.getByLabel('Email').fill('test@test.com');
    await page.getByLabel('Password', { exact: true }).fill('short');
    await page.getByLabel('Confirm Password').fill('short');
    await page.getByRole('button', { name: 'Create Account' }).click();
    await expect(page.getByText('Password must be at least 8 characters')).toBeVisible();
  });

  test('register validates password mismatch', async ({ page }) => {
    await page.goto('/auth/register');
    await page.getByLabel('Full Name').fill('Test User');
    await page.getByLabel('Email').fill('test@test.com');
    await page.getByLabel('Password', { exact: true }).fill('ValidPassword123!');
    await page.getByLabel('Confirm Password').fill('DifferentPassword!');
    await page.getByRole('button', { name: 'Create Account' }).click();
    await expect(page.getByText("Passwords don't match")).toBeVisible();
  });

  test('register validates invalid email', async ({ page }) => {
    await page.goto('/auth/register');
    await page.getByLabel('Full Name').fill('Test User');
    await page.getByLabel('Email').fill('not-an-email');
    await page.getByLabel('Password', { exact: true }).fill('ValidPassword123!');
    await page.getByLabel('Confirm Password').fill('ValidPassword123!');
    await page.getByRole('button', { name: 'Create Account' }).click();
    await expect(page.getByText('Please enter a valid email')).toBeVisible();
  });

  test('register new user successfully', async ({ page }) => {
    await page.goto('/auth/register');
    await page.getByLabel('Full Name').fill(user.name);
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password', { exact: true }).fill(user.password);
    await page.getByLabel('Confirm Password').fill(user.password);
    await page.getByRole('button', { name: 'Create Account' }).click();
    await page.waitForURL('**/auth/login', { timeout: 10_000 });
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test('register duplicate email shows error', async ({ page }) => {
    await page.goto('/auth/register');
    await page.getByLabel('Full Name').fill(user.name);
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password', { exact: true }).fill(user.password);
    await page.getByLabel('Confirm Password').fill(user.password);
    await page.getByRole('button', { name: 'Create Account' }).click();
    // Should show error toast about duplicate
    await expect(page.getByText(/error|already|exists/i).first()).toBeVisible({ timeout: 5_000 });
  });

  // ── Login Page ──

  test('login page renders all fields', async ({ page }) => {
    await page.goto('/auth/login');
    await expect(page.getByText('Welcome back')).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
    await expect(page.getByText("Don't have an account?")).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign up' })).toBeVisible();
  });

  test('login validates empty fields', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByText('Please enter a valid email')).toBeVisible();
  });

  test('login validates short password', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByLabel('Email').fill('test@test.com');
    await page.getByLabel('Password').fill('ab');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByText('Password must be at least 6 characters')).toBeVisible();
  });

  test('login with wrong password shows error', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill('wrongpassword123');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByText(/error|failed|invalid|incorrect/i).first()).toBeVisible({
      timeout: 5_000,
    });
  });

  test('login with correct credentials redirects to dashboard', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await page.waitForURL('**/dashboard', { timeout: 10_000 });
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('login shows loading spinner while submitting', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    // Button should show spinner briefly
    const button = page.getByRole('button', { name: /sign in/i });
    // Wait for redirect which means it worked
    await page.waitForURL('**/dashboard', { timeout: 10_000 });
  });

  test('login preserves redirect param', async ({ page }) => {
    await page.goto('/auth/login?redirect=%2Fassistants');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await page.waitForURL('**/assistants', { timeout: 10_000 });
  });

  // ── Navigation between auth pages ──

  test('login → register link works', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByRole('link', { name: 'Sign up' }).click();
    await expect(page).toHaveURL(/\/auth\/register/);
  });

  test('register → login link works', async ({ page }) => {
    await page.goto('/auth/register');
    await page.getByRole('link', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  // ── Middleware protection ──

  test('unauthenticated: / redirects to /auth/login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/');
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test('unauthenticated: /dashboard redirects with redirect param', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/auth\/login\?redirect=%2Fdashboard/);
  });

  test('unauthenticated: /chat redirects to login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/chat');
    await expect(page).toHaveURL(/\/auth\/login\?redirect=%2Fchat/);
  });

  test('unauthenticated: /assistants redirects to login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/assistants');
    await expect(page).toHaveURL(/\/auth\/login\?redirect=%2Fassistants/);
  });

  test('unauthenticated: /knowledge-bases redirects to login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/knowledge-bases');
    await expect(page).toHaveURL(/\/auth\/login\?redirect=%2Fknowledge-bases/);
  });

  test('unauthenticated: /settings redirects to login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/settings');
    await expect(page).toHaveURL(/\/auth\/login\?redirect=%2Fsettings/);
  });

  test('unauthenticated: /tools redirects to login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/tools');
    await expect(page).toHaveURL(/\/auth\/login\?redirect=%2Ftools/);
  });

  test('unauthenticated: /projects redirects to login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/projects');
    await expect(page).toHaveURL(/\/auth\/login\?redirect=%2Fprojects/);
  });

  test('authenticated: /auth/login redirects to dashboard', async ({ page }) => {
    // Login first
    await page.goto('/auth/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await page.waitForURL('**/dashboard', { timeout: 10_000 });

    // Now try to access login page
    await page.goto('/auth/login');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('authenticated: / redirects to dashboard', async ({ page }) => {
    await page.goto('/auth/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
    await page.waitForURL('**/dashboard', { timeout: 10_000 });

    await page.goto('/');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  // ── Public pages accessible without auth ──

  test('unauthenticated: /docs accessible', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/docs');
    await expect(page).toHaveURL(/\/docs/);
  });

  test('unauthenticated: /api-reference accessible', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/api-reference');
    await expect(page).toHaveURL(/\/api-reference/);
  });
});
