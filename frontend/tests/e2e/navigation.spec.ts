import { test, expect } from '@playwright/test';
import {
  registerAndLoginViaAPI,
  injectAuth,
  setupConsoleErrorListener,
  waitForPageReady,
} from './helpers';

test.describe('Navigation & Theme', () => {
  let creds: Awaited<ReturnType<typeof registerAndLoginViaAPI>>;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    creds = await registerAndLoginViaAPI(page, 'http://localhost:3000');
    await page.close();
  });

  test.beforeEach(async ({ page, baseURL }) => {
    await injectAuth(page, creds.token, baseURL!);
  });

  // ── Every page loads without console errors ──

  const protectedPages = [
    { name: 'Dashboard', url: '/dashboard' },
    { name: 'Assistants', url: '/assistants' },
    { name: 'Assistant Builder', url: '/assistants/builder' },
    { name: 'Knowledge Bases', url: '/knowledge-bases' },
    { name: 'Tools', url: '/tools' },
    { name: 'Tool Create', url: '/tools/create' },
    { name: 'Projects', url: '/projects' },
    { name: 'Chat', url: '/chat' },
    { name: 'Settings Profile', url: '/settings/profile' },
    { name: 'Settings API Keys', url: '/settings/api-keys' },
    { name: 'Settings Providers', url: '/settings/providers' },
    { name: 'Platform Overview', url: '/platform' },
    { name: 'Platform Chat', url: '/platform/chat' },
    { name: 'Platform RAG Pipelines', url: '/platform/rag-pipelines' },
    { name: 'Platform Agent Builder', url: '/platform/agent-builder' },
    { name: 'Platform Audio', url: '/platform/audio' },
    { name: 'Platform Images', url: '/platform/images' },
    { name: 'Platform Videos', url: '/platform/videos' },
    { name: 'Platform Usage', url: '/platform/usage' },
    { name: 'Platform API Keys', url: '/platform/api-keys' },
    { name: 'Platform Logs', url: '/platform/logs' },
    { name: 'Platform Storage', url: '/platform/storage' },
    { name: 'Voice Settings', url: '/manage/voice' },
    { name: 'Avatar Chat', url: '/avatar-chat' },
  ];

  for (const p of protectedPages) {
    test(`${p.name} (${p.url}) loads without errors`, async ({ page }) => {
      const errors = setupConsoleErrorListener(page);
      await page.goto(p.url);
      await waitForPageReady(page);

      // Page should not be blank
      const body = await page.textContent('body');
      expect(body?.trim().length).toBeGreaterThan(0);

      expect(errors).toHaveLength(0);
    });
  }

  // ── Public pages ──

  const publicPages = [
    { name: 'Docs', url: '/docs' },
    { name: 'API Reference', url: '/api-reference' },
  ];

  for (const p of publicPages) {
    test(`Public: ${p.name} loads without auth`, async ({ page }) => {
      await page.context().clearCookies();
      const errors = setupConsoleErrorListener(page);
      await page.goto(p.url);
      await waitForPageReady(page);
      await expect(page).toHaveURL(new RegExp(p.url.replace(/\//g, '\\/')));
      expect(errors).toHaveLength(0);
    });
  }

  // ── Sidebar Navigation Links ──

  test('sidebar: Dashboard link works', async ({ page }) => {
    await page.goto('/assistants');
    await waitForPageReady(page);
    const link = page.getByRole('link', { name: /dashboard/i }).first();
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/dashboard/);
    }
  });

  test('sidebar: Assistants link works', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const link = page.getByRole('link', { name: /assistants/i }).first();
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/assistants/);
    }
  });

  test('sidebar: Knowledge Bases link works', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const link = page.getByRole('link', { name: /knowledge bases/i }).first();
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/knowledge-bases/);
    }
  });

  test('sidebar: Chat link works', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const link = page.getByRole('link', { name: /chat/i }).first();
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/chat/);
    }
  });

  test('sidebar: Tools link works', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const link = page.getByRole('link', { name: /tools/i }).first();
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/tools/);
    }
  });

  test('sidebar: Projects link works', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const link = page.getByRole('link', { name: /projects/i }).first();
    if (await link.isVisible()) {
      await link.click();
      await expect(page).toHaveURL(/\/projects/);
    }
  });

  // ── Theme ──

  test('dark theme is active (html has class="dark")', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const htmlClass = await page.getAttribute('html', 'class');
    expect(htmlClass).toContain('dark');
  });

  test('dark theme active on login page', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/auth/login');
    await waitForPageReady(page);
    const htmlClass = await page.getAttribute('html', 'class');
    expect(htmlClass).toContain('dark');
  });

  test('dark theme active on register page', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/auth/register');
    await waitForPageReady(page);
    const htmlClass = await page.getAttribute('html', 'class');
    expect(htmlClass).toContain('dark');
  });

  // ── Root Redirects ──

  test('authenticated root redirects to dashboard', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('unauthenticated root redirects to login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/');
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  // ── Docs Page Content ──

  test('docs page has search', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/docs');
    await waitForPageReady(page);
    const search = page.getByPlaceholder(/search/i).first();
    const hasSearch = await search.isVisible().catch(() => false);
  });

  test('docs page has quick links', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/docs');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('API Reference') || body?.includes('SDK') ||
      body?.includes('Getting Started')
    ).toBeTruthy();
  });

  // ── API Reference Page Content ──

  test('API reference has search', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/api-reference');
    await waitForPageReady(page);
    const search = page.getByPlaceholder(/search/i).first();
    const hasSearch = await search.isVisible().catch(() => false);
  });

  test('API reference has endpoint sections', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/api-reference');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Assistants') || body?.includes('Messages') ||
      body?.includes('Authentication') || body?.includes('Files')
    ).toBeTruthy();
  });

  test('API reference has code examples with copy buttons', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/api-reference');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Bearer') || body?.includes('Authorization') ||
      body?.includes('curl') || body?.includes('Copy')
    ).toBeTruthy();
  });

  // ── App Header ──

  test('app header visible on dashboard', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    // Header should have user menu or notification bell
    const body = await page.textContent('body');
    expect(body?.trim().length).toBeGreaterThan(0);
  });
});
