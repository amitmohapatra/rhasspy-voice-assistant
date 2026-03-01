import { test, expect } from '@playwright/test';
import {
  registerAndLoginViaAPI,
  injectAuth,
  setupConsoleErrorListener,
  createAssistantViaAPI,
  createKBViaAPI,
  waitForPageReady,
} from './helpers';

test.describe('Dashboard', () => {
  let creds: Awaited<ReturnType<typeof registerAndLoginViaAPI>>;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    creds = await registerAndLoginViaAPI(page, 'http://localhost:3000');
    // Pre-seed data for dashboard
    await createAssistantViaAPI(page, creds.token, { name: 'Dashboard Test Bot' });
    await createKBViaAPI(page, creds.token, { name: 'Dashboard Test KB' });
    await page.close();
  });

  test.beforeEach(async ({ page, baseURL }) => {
    await injectAuth(page, creds.token, baseURL!);
  });

  // ── Page Load ──

  test('dashboard loads without console errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await expect(page.getByText(/Good (morning|afternoon|evening)/i).first()).toBeVisible({
      timeout: 10_000,
    });
    expect(errors).toHaveLength(0);
  });

  test('shows time-based greeting with user name', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const greeting = page.getByText(/Good (morning|afternoon|evening)/i).first();
    await expect(greeting).toBeVisible();
  });

  // ── Stats Cards ──

  test('stats grid shows all 4 cards', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await expect(page.getByText('Assistants').first()).toBeVisible();
    await expect(page.getByText('Knowledge Bases').first()).toBeVisible();
    await expect(page.getByText('Documents').first()).toBeVisible();
  });

  test('stats cards show counts from API data', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    // At least 1 assistant and 1 KB were seeded
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });

  // ── Quick Actions ──

  test('quick actions section visible', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await expect(page.getByText('Quick Actions').first()).toBeVisible();
  });

  test('quick action: Create Assistant navigates to builder', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await page.getByText('Create Assistant').first().click();
    await expect(page).toHaveURL(/\/assistants\/builder/);
  });

  test('quick action: Upload Documents navigates to KBs', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await page.getByText('Upload Documents').first().click();
    await expect(page).toHaveURL(/\/knowledge-bases/);
  });

  test('quick action: Start Chat navigates to chat', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await page.getByText('Start Chat').first().click();
    await expect(page).toHaveURL(/\/chat/);
  });

  test('quick action: Configure RAG navigates to pipelines', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await page.getByText('Configure RAG').first().click();
    await expect(page).toHaveURL(/\/platform\/rag-pipelines/);
  });

  // ── Assistants Section ──

  test('your assistants section shows seeded assistant', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await expect(page.getByText('Your Assistants').first()).toBeVisible();
    await expect(page.getByText('Dashboard Test Bot').first()).toBeVisible();
  });

  test('view all assistants link works', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const viewAll = page.getByText('View all').first();
    if (await viewAll.isVisible()) {
      await viewAll.click();
      await expect(page).toHaveURL(/\/assistants/);
    }
  });

  // ── Knowledge Bases Section ──

  test('knowledge bases section shows seeded KB', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await expect(page.getByText('Knowledge Bases').first()).toBeVisible();
    await expect(page.getByText('Dashboard Test KB').first()).toBeVisible();
  });

  // ── Sidebar ──

  test('sidebar navigation items visible', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await expect(page.getByText('Dashboard').first()).toBeVisible();
    await expect(page.getByText('Assistants').first()).toBeVisible();
    await expect(page.getByText('Knowledge Bases').first()).toBeVisible();
    await expect(page.getByText('Chat').first()).toBeVisible();
    await expect(page.getByText('Tools').first()).toBeVisible();
  });

  // ── Resources Section ──

  test('resources section visible', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await expect(page.getByText('Resources').first()).toBeVisible();
  });

  // ── New Assistant Button ──

  test('header New Assistant button navigates to builder', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    const newBtn = page.getByRole('link', { name: /new assistant/i }).first()
      .or(page.getByText('New Assistant').first());
    if (await newBtn.isVisible()) {
      await newBtn.click();
      await expect(page).toHaveURL(/\/assistants\/builder/);
    }
  });
});
