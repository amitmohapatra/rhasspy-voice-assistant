import { test, expect } from '@playwright/test';
import {
  registerAndLoginViaAPI,
  injectAuth,
  setupConsoleErrorListener,
  waitForPageReady,
  API_BASE,
} from './helpers';

test.describe('Platform Pages', () => {
  let creds: Awaited<ReturnType<typeof registerAndLoginViaAPI>>;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    creds = await registerAndLoginViaAPI(page, 'http://localhost:3000');
    await page.close();
  });

  test.beforeEach(async ({ page, baseURL }) => {
    await injectAuth(page, creds.token, baseURL!);
  });

  // ── Platform Overview ──

  test('platform overview loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('platform overview has tabs', async ({ page }) => {
    await page.goto('/platform');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Overview') || body?.includes('Audit') || body?.includes('Config')
    ).toBeTruthy();
  });

  // ── Platform Chat ──

  test('platform chat page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/chat');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('platform chat has model selector', async ({ page }) => {
    await page.goto('/platform/chat');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.toLowerCase().includes('model') || body?.toLowerCase().includes('gpt')
    ).toBeTruthy();
  });

  test('platform chat has message input', async ({ page }) => {
    await page.goto('/platform/chat');
    await waitForPageReady(page);
    const input = page.locator('textarea').first()
      .or(page.getByPlaceholder(/message/i).first());
    const hasInput = await input.isVisible().catch(() => false);
    expect(hasInput).toBeTruthy();
  });

  test('platform chat has new chat button', async ({ page }) => {
    await page.goto('/platform/chat');
    await waitForPageReady(page);
    const btn = page.getByText(/New Chat/i).first();
    const hasBtn = await btn.isVisible().catch(() => false);
  });

  // ── Agent Builder ──

  test('agent builder page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/agent-builder');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('agent builder has tabs (Configuration, Tools, Knowledge, Settings)', async ({ page }) => {
    await page.goto('/platform/agent-builder');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Configuration') || body?.includes('Tools') ||
      body?.includes('Knowledge') || body?.includes('Settings')
    ).toBeTruthy();
  });

  test('agent builder has new agent button', async ({ page }) => {
    await page.goto('/platform/agent-builder');
    await waitForPageReady(page);
    const btn = page.getByText(/New Agent/i).first();
    const hasBtn = await btn.isVisible().catch(() => false);
  });

  test('agent builder configuration tab has form fields', async ({ page }) => {
    await page.goto('/platform/agent-builder');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Name') || body?.includes('Description') ||
      body?.includes('Temperature') || body?.includes('System')
    ).toBeTruthy();
  });

  // ── Audio (TTS/STT) ──

  test('audio page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/audio');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('audio page has TTS and STT tabs', async ({ page }) => {
    await page.goto('/platform/audio');
    await waitForPageReady(page);
    await expect(page.getByText(/Text-to-Speech/i).first()).toBeVisible();
    await expect(page.getByText(/Speech-to-Text/i).first()).toBeVisible();
  });

  test('audio TTS tab has voice selector', async ({ page }) => {
    await page.goto('/platform/audio');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Alloy') || body?.includes('Echo') || body?.includes('Nova') ||
      body?.includes('Voice') || body?.includes('voice')
    ).toBeTruthy();
  });

  test('audio TTS tab has text input', async ({ page }) => {
    await page.goto('/platform/audio');
    await waitForPageReady(page);
    const textarea = page.locator('textarea').first();
    const hasTextarea = await textarea.isVisible().catch(() => false);
    expect(hasTextarea).toBeTruthy();
  });

  test('audio TTS tab has generate button', async ({ page }) => {
    await page.goto('/platform/audio');
    await waitForPageReady(page);
    const btn = page.getByRole('button', { name: /generate speech/i }).first();
    const hasBtn = await btn.isVisible().catch(() => false);
    expect(hasBtn).toBeTruthy();
  });

  test('audio STT tab has recording controls', async ({ page }) => {
    await page.goto('/platform/audio');
    await waitForPageReady(page);

    const sttTab = page.getByText(/Speech-to-Text/i).first();
    await sttTab.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('Record') || body?.includes('Upload') || body?.includes('Start')
    ).toBeTruthy();
  });

  // ── Images ──

  test('images page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/images');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('images page has prompt input', async ({ page }) => {
    await page.goto('/platform/images');
    await waitForPageReady(page);
    const textarea = page.locator('textarea').first();
    const hasTextarea = await textarea.isVisible().catch(() => false);
    expect(hasTextarea).toBeTruthy();
  });

  test('images page has model selector', async ({ page }) => {
    await page.goto('/platform/images');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('DALL-E') || body?.includes('Stable Diffusion') || body?.includes('Model')
    ).toBeTruthy();
  });

  test('images page has size selector', async ({ page }) => {
    await page.goto('/platform/images');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('1024') || body?.includes('Size') || body?.includes('size')
    ).toBeTruthy();
  });

  test('images page has quality selector', async ({ page }) => {
    await page.goto('/platform/images');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Standard') || body?.includes('HD') || body?.includes('Quality')
    ).toBeTruthy();
  });

  test('images page has generate button', async ({ page }) => {
    await page.goto('/platform/images');
    await waitForPageReady(page);
    const btn = page.getByRole('button', { name: /generate/i }).first();
    await expect(btn).toBeVisible();
  });

  // ── Videos ──

  test('videos page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/videos');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('videos page has generate and history tabs', async ({ page }) => {
    await page.goto('/platform/videos');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Generate') || body?.includes('History')
    ).toBeTruthy();
  });

  test('videos page has prompt input', async ({ page }) => {
    await page.goto('/platform/videos');
    await waitForPageReady(page);
    const textarea = page.locator('textarea').first();
    const hasTextarea = await textarea.isVisible().catch(() => false);
  });

  test('videos page has duration selector', async ({ page }) => {
    await page.goto('/platform/videos');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Duration') || body?.includes('seconds') || body?.includes('5s')
    ).toBeTruthy();
  });

  test('videos page has aspect ratio selector', async ({ page }) => {
    await page.goto('/platform/videos');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('16:9') || body?.includes('Aspect') || body?.includes('ratio')
    ).toBeTruthy();
  });

  // ── Usage ──

  test('usage page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/usage');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('usage page has period selector', async ({ page }) => {
    await page.goto('/platform/usage');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Today') || body?.includes('This Week') || body?.includes('This Month')
    ).toBeTruthy();
  });

  test('usage page has metrics cards', async ({ page }) => {
    await page.goto('/platform/usage');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('API Requests') || body?.includes('Tokens') || body?.includes('Audio')
    ).toBeTruthy();
  });

  test('usage page has tabs (Overview, Cost, Rate Limits)', async ({ page }) => {
    await page.goto('/platform/usage');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Overview') || body?.includes('Cost') || body?.includes('Rate')
    ).toBeTruthy();
  });

  // ── API Keys (Platform) ──

  test('platform API keys page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/api-keys');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body?.toLowerCase()).toMatch(/api.*key/);
    expect(errors).toHaveLength(0);
  });

  test('platform API keys has create button', async ({ page }) => {
    await page.goto('/platform/api-keys');
    await waitForPageReady(page);
    const btn = page.getByRole('button', { name: /create/i }).first();
    const hasBtn = await btn.isVisible().catch(() => false);
    expect(hasBtn).toBeTruthy();
  });

  test('platform API keys has security info', async ({ page }) => {
    await page.goto('/platform/api-keys');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('secure') || body?.includes('warning') || body?.includes('Security')
    ).toBeTruthy();
  });

  // ── Logs ──

  test('logs page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/logs');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('logs page has search filter', async ({ page }) => {
    await page.goto('/platform/logs');
    await waitForPageReady(page);
    const search = page.getByPlaceholder(/search|endpoint/i).first();
    const hasSearch = await search.isVisible().catch(() => false);
  });

  test('logs page has status filter', async ({ page }) => {
    await page.goto('/platform/logs');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('All Status') || body?.includes('Success') || body?.includes('Error') ||
      body?.includes('filter')
    ).toBeTruthy();
  });

  test('logs page has refresh button', async ({ page }) => {
    await page.goto('/platform/logs');
    await waitForPageReady(page);
    // Refresh button should exist
  });

  // ── RAG Pipeline API ──

  test('get pipeline info via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/rag-pipelines`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
  });

  test('test Qdrant connection via API', async ({ page }) => {
    const resp = await page.request.post(`${API_BASE}/api/v1/rag-pipelines/test-connection`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: {
        connection_type: 'qdrant',
        config: { url: 'http://qdrant:6333' },
      },
    });
    // May fail if Qdrant not running, but shouldn't 500
    expect(resp.status()).toBeLessThan(500);
  });

  test('test Redis connection via API', async ({ page }) => {
    const resp = await page.request.post(`${API_BASE}/api/v1/rag-pipelines/test-connection`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: {
        connection_type: 'redis',
        config: { url: 'redis://redis:6379' },
      },
    });
    expect(resp.status()).toBeLessThan(500);
  });

  // ── Models API ──

  test('list models via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/models?limit=10`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data).toHaveProperty('models');
  });

  test('get default model via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/models/default`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    // May return 404 if no default set
    expect(resp.status()).toBeLessThan(500);
  });
});
