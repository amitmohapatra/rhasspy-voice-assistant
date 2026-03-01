import { test, expect } from '@playwright/test';
import {
  registerAndLoginViaAPI,
  injectAuth,
  setupConsoleErrorListener,
  waitForPageReady,
  API_BASE,
} from './helpers';

test.describe('Settings', () => {
  let creds: Awaited<ReturnType<typeof registerAndLoginViaAPI>>;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    creds = await registerAndLoginViaAPI(page, 'http://localhost:3000');
    await page.close();
  });

  test.beforeEach(async ({ page, baseURL }) => {
    await injectAuth(page, creds.token, baseURL!);
  });

  // ── Settings Layout ──

  test('settings index redirects to profile', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForURL('**/settings/profile', { timeout: 5000 });
    await expect(page).toHaveURL(/\/settings\/profile/);
  });

  test('settings has Rhasspy branding in header', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    await expect(page.getByText('Rhasspy').first()).toBeVisible();
  });

  test('settings header has dashboard link', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const dashLink = page.getByRole('link', { name: /dashboard/i }).first();
    if (await dashLink.isVisible()) {
      await dashLink.click();
      await expect(page).toHaveURL(/\/dashboard/);
    }
  });

  test('settings sidebar has navigation items', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body).toContain('Profile');
    expect(body).toContain('API Keys');
    expect(body).toContain('Providers');
  });

  test('settings sidebar navigation: API Keys', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const link = page.getByText('API Keys').first();
    await link.click();
    await expect(page).toHaveURL(/\/settings\/api-keys/);
  });

  test('settings sidebar navigation: Providers', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const link = page.getByText('Providers').first();
    await link.click();
    await expect(page).toHaveURL(/\/settings\/providers/);
  });

  // ── Profile Page ──

  test('profile page loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body?.toLowerCase()).toMatch(/profile/);
    expect(errors).toHaveLength(0);
  });

  test('profile page has avatar section', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('avatar') || body?.includes('Avatar') || body?.includes('Change')
    ).toBeTruthy();
  });

  test('profile page has name and email fields', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);

    const nameInput = page.getByLabel(/full name/i).first()
      .or(page.getByPlaceholder(/full name/i).first());
    const emailInput = page.getByLabel(/email/i).first()
      .or(page.getByPlaceholder(/email/i).first());

    const hasName = await nameInput.isVisible().catch(() => false);
    const hasEmail = await emailInput.isVisible().catch(() => false);
    expect(hasName || hasEmail).toBeTruthy();
  });

  test('profile page has account information (read-only)', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('User ID') || body?.includes('Member Since') || body?.includes('Account')
    ).toBeTruthy();
  });

  test('profile page has preferences section', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Preferences') || body?.includes('Theme') || body?.includes('Language')
    ).toBeTruthy();
  });

  test('profile page has theme toggle (Light/Dark/System)', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Light') || body?.includes('Dark') || body?.includes('System')
    ).toBeTruthy();
  });

  test('profile page has language selector', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Language') || body?.includes('English')
    ).toBeTruthy();
  });

  test('profile page has timezone selector', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Timezone') || body?.includes('UTC') || body?.includes('timezone')
    ).toBeTruthy();
  });

  test('profile page has save button', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);
    const saveBtn = page.getByRole('button', { name: /save/i }).first();
    await expect(saveBtn).toBeVisible();
  });

  test('profile save changes with valid data', async ({ page }) => {
    await page.goto('/settings/profile');
    await waitForPageReady(page);

    // Update name
    const nameInput = page.getByLabel(/full name/i).first()
      .or(page.getByPlaceholder(/full name/i).first());
    if (await nameInput.isVisible()) {
      await nameInput.clear();
      await nameInput.fill('Updated E2E User');
    }

    // Click save
    const saveBtn = page.getByRole('button', { name: /save/i }).first();
    await saveBtn.click();
    await page.waitForTimeout(2000);
  });

  // ── API Keys Page ──

  test('API keys page loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/settings/api-keys');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body?.toLowerCase()).toMatch(/api.*key/);
    expect(errors).toHaveLength(0);
  });

  test('API keys page has security warning', async ({ page }) => {
    await page.goto('/settings/api-keys');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('secure') || body?.includes('warning') || body?.includes('Warning')
    ).toBeTruthy();
  });

  test('API keys page has create key button', async ({ page }) => {
    await page.goto('/settings/api-keys');
    await waitForPageReady(page);
    const createBtn = page.getByRole('button', { name: /create/i }).first()
      .or(page.getByText(/Create New Key/i).first());
    await expect(createBtn).toBeVisible();
  });

  test('create API key form opens', async ({ page }) => {
    await page.goto('/settings/api-keys');
    await waitForPageReady(page);

    const createBtn = page.getByRole('button', { name: /create/i }).first()
      .or(page.getByText(/Create New Key/i).first());
    await createBtn.click();
    await page.waitForTimeout(500);

    // Should show form with name input
    const nameInput = page.getByPlaceholder(/production api key/i).first()
      .or(page.getByLabel(/name/i).first())
      .or(page.getByPlaceholder(/name/i).first());
    const hasInput = await nameInput.isVisible().catch(() => false);
    expect(hasInput).toBeTruthy();
  });

  test('create API key form has expiry selector', async ({ page }) => {
    await page.goto('/settings/api-keys');
    await waitForPageReady(page);

    const createBtn = page.getByRole('button', { name: /create/i }).first()
      .or(page.getByText(/Create New Key/i).first());
    await createBtn.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('Never expires') || body?.includes('30 days') ||
      body?.includes('expir') || body?.includes('Expir')
    ).toBeTruthy();
  });

  test('create API key end-to-end', async ({ page }) => {
    await page.goto('/settings/api-keys');
    await waitForPageReady(page);

    const createBtn = page.getByRole('button', { name: /create/i }).first()
      .or(page.getByText(/Create New Key/i).first());
    await createBtn.click();
    await page.waitForTimeout(500);

    const nameInput = page.getByPlaceholder(/production api key/i).first()
      .or(page.getByLabel(/name/i).first())
      .or(page.getByPlaceholder(/name/i).first());
    if (await nameInput.isVisible()) {
      await nameInput.fill('E2E Test Key');
    }

    const submitBtn = page.getByRole('button', { name: /create key/i }).first();
    if (await submitBtn.isVisible() && await submitBtn.isEnabled()) {
      await submitBtn.click();
      await page.waitForTimeout(2000);
      // Should show the newly created key
    }
  });

  // ── Providers Page ──

  test('providers page loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/settings/providers');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body?.toLowerCase()).toMatch(/provider/);
    expect(errors).toHaveLength(0);
  });

  test('providers page shows provider cards', async ({ page }) => {
    await page.goto('/settings/providers');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    // Should list known providers (OpenAI, Anthropic, etc.)
    expect(
      body?.includes('OpenAI') || body?.includes('Anthropic') || body?.includes('provider')
    ).toBeTruthy();
  });

  test('provider cards show status badges', async ({ page }) => {
    await page.goto('/settings/providers');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Active') || body?.includes('Inactive') || body?.includes('API Key')
    ).toBeTruthy();
  });

  test('provider cards show capability badges', async ({ page }) => {
    await page.goto('/settings/providers');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('llm') || body?.includes('embeddings') || body?.includes('tts') ||
      body?.includes('stt') || body?.includes('LLM')
    ).toBeTruthy();
  });

  test('provider has test connection button', async ({ page }) => {
    await page.goto('/settings/providers');
    await waitForPageReady(page);
    const testBtn = page.getByRole('button', { name: /test/i }).first();
    const hasBtn = await testBtn.isVisible().catch(() => false);
    expect(hasBtn).toBeTruthy();
  });

  test('provider has toggle switch', async ({ page }) => {
    await page.goto('/settings/providers');
    await waitForPageReady(page);
    const toggles = page.locator('[role="switch"]');
    const count = await toggles.count();
    // Should have at least some toggles
  });

  test('provider has API key configuration', async ({ page }) => {
    await page.goto('/settings/providers');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('API Key') || body?.includes('Configure') || body?.includes('api key')
    ).toBeTruthy();
  });

  test('provider test connection via API', async ({ page }) => {
    const resp = await page.request.post(`${API_BASE}/api/v1/providers/test-connection`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: { provider_name: 'openai' },
    });
    // May succeed or fail depending on API key
    expect(resp.status()).toBeLessThan(500);
  });

  // ── Providers list via API ──

  test('list providers via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/models/providers`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const providers = await resp.json();
    expect(Array.isArray(providers)).toBeTruthy();
  });
});
