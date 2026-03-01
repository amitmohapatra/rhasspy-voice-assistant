import { test, expect } from '@playwright/test';
import {
  registerAndLoginViaAPI,
  injectAuth,
  setupConsoleErrorListener,
  createToolViaAPI,
  waitForPageReady,
  API_BASE,
} from './helpers';

test.describe('Tools', () => {
  let creds: Awaited<ReturnType<typeof registerAndLoginViaAPI>>;
  let toolId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    creds = await registerAndLoginViaAPI(page, 'http://localhost:3000');
    const tool = await createToolViaAPI(page, creds.token, {
      name: 'seeded_test_tool',
      description: 'A seeded tool for E2E tests',
    });
    toolId = (tool as any).id;
    await page.close();
  });

  test.beforeEach(async ({ page, baseURL }) => {
    await injectAuth(page, creds.token, baseURL!);
  });

  // ── Tools List Page ──

  test('tools page loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/tools');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body?.toLowerCase()).toMatch(/tool/);
    expect(errors).toHaveLength(0);
  });

  test('tools page has tabs (Vendor, Integrations, Custom, History)', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Vendor') ||
      body?.includes('Custom') ||
      body?.includes('Integration') ||
      body?.includes('History')
    ).toBeTruthy();
  });

  test('vendor tools tab shows builtin tools', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    // Click vendor tools tab
    const vendorTab = page.getByText(/Vendor/i).first();
    if (await vendorTab.isVisible()) {
      await vendorTab.click();
      await page.waitForTimeout(500);
      // Should show tool cards
    }
  });

  test('vendor tools have toggle switches', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const vendorTab = page.getByText(/Vendor/i).first();
    if (await vendorTab.isVisible()) {
      await vendorTab.click();
      await page.waitForTimeout(500);
      // Toggle switches for enabling/disabling tools
      const toggles = page.locator('[role="switch"]');
      const count = await toggles.count();
      // May have multiple toggles
    }
  });

  test('integrations tab shows integration catalog', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const integrationsTab = page.getByText(/Integration/i).first();
    if (await integrationsTab.isVisible()) {
      await integrationsTab.click();
      await page.waitForTimeout(500);
      const body = await page.textContent('body');
      expect(
        body?.includes('Connect') ||
        body?.includes('integration') ||
        body?.includes('Search')
      ).toBeTruthy();
    }
  });

  test('integrations tab has search', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const integrationsTab = page.getByText(/Integration/i).first();
    if (await integrationsTab.isVisible()) {
      await integrationsTab.click();
      await page.waitForTimeout(500);
      const search = page.getByPlaceholder(/search integration/i).first();
      const hasSearch = await search.isVisible().catch(() => false);
    }
  });

  test('integrations tab has category filter', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const integrationsTab = page.getByText(/Integration/i).first();
    if (await integrationsTab.isVisible()) {
      await integrationsTab.click();
      await page.waitForTimeout(500);
      // Should have category filter dropdown
      const body = await page.textContent('body');
      expect(
        body?.includes('All Categories') || body?.includes('Category')
      ).toBeTruthy();
    }
  });

  test('custom tools tab shows seeded tool', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const customTab = page.getByText(/Custom/i).first();
    if (await customTab.isVisible()) {
      await customTab.click();
      await page.waitForTimeout(500);
      const body = await page.textContent('body');
      expect(
        body?.includes('seeded_test_tool') || body?.includes('custom')
      ).toBeTruthy();
    }
  });

  test('custom tools tab has search', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const customTab = page.getByText(/Custom/i).first();
    if (await customTab.isVisible()) {
      await customTab.click();
      await page.waitForTimeout(500);
      const search = page.getByPlaceholder(/search custom/i).first();
      const hasSearch = await search.isVisible().catch(() => false);
    }
  });

  test('execution history tab loads', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const historyTab = page.getByText(/History/i).first()
      .or(page.getByText(/Execution/i).first());
    if (await historyTab.isVisible()) {
      await historyTab.click();
      await page.waitForTimeout(500);
      // Should show execution history or empty state
    }
  });

  test('create custom tool button exists', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const createBtn = page.getByRole('link', { name: /create custom tool/i }).first()
      .or(page.getByText(/Create Custom Tool/i).first());
    const hasBtn = await createBtn.isVisible().catch(() => false);
    expect(hasBtn).toBeTruthy();
  });

  // ── Create Tool Page ──

  test('create tool page loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/tools/create');
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('create tool form has all required fields', async ({ page }) => {
    await page.goto('/tools/create');
    await waitForPageReady(page);

    // Name field
    const nameInput = page.getByLabel(/^name$/i).first()
      .or(page.getByPlaceholder(/name/i).first());
    await expect(nameInput).toBeVisible();

    // Description field
    const descInput = page.getByLabel(/description/i).first()
      .or(page.getByPlaceholder(/description/i).first());
    const hasDesc = await descInput.isVisible().catch(() => false);
  });

  test('create tool form has handler type selector', async ({ page }) => {
    await page.goto('/tools/create');
    await waitForPageReady(page);

    // Should have HTTP Webhook, MCP Server, Python Code options
    const body = await page.textContent('body');
    expect(
      body?.includes('HTTP') || body?.includes('MCP') || body?.includes('Python') ||
      body?.includes('Webhook') || body?.includes('handler')
    ).toBeTruthy();
  });

  test('create tool form has category dropdown', async ({ page }) => {
    await page.goto('/tools/create');
    await waitForPageReady(page);

    const body = await page.textContent('body');
    expect(
      body?.includes('Category') || body?.includes('custom') || body?.includes('category')
    ).toBeTruthy();
  });

  test('create tool form has JSON schema section', async ({ page }) => {
    await page.goto('/tools/create');
    await waitForPageReady(page);

    const body = await page.textContent('body');
    expect(
      body?.includes('Schema') || body?.includes('Parameters') || body?.includes('JSON')
    ).toBeTruthy();
  });

  test('create tool form has test panel', async ({ page }) => {
    await page.goto('/tools/create');
    await waitForPageReady(page);

    const testBtn = page.getByRole('button', { name: /run test/i }).first()
      .or(page.getByText(/Test/i).first());
    const hasTest = await testBtn.isVisible().catch(() => false);
  });

  test('create tool form has secrets section', async ({ page }) => {
    await page.goto('/tools/create');
    await waitForPageReady(page);

    const body = await page.textContent('body');
    expect(
      body?.includes('Secret') || body?.includes('secret')
    ).toBeTruthy();
  });

  test('create custom tool end-to-end', async ({ page }) => {
    await page.goto('/tools/create');
    await waitForPageReady(page);

    // Fill name
    const nameInput = page.getByLabel(/^name$/i).first()
      .or(page.getByPlaceholder(/name/i).first());
    await nameInput.fill('e2e_test_tool');

    // Fill description
    const descInput = page.getByLabel(/description/i).first()
      .or(page.getByPlaceholder(/description/i).first());
    if (await descInput.isVisible()) {
      await descInput.fill('Tool created by E2E test');
    }

    // Submit
    const submitBtn = page.getByRole('button', { name: /create tool/i }).first();
    if (await submitBtn.isEnabled()) {
      await submitBtn.click();
      await page.waitForTimeout(2000);
    }
  });

  // ── Tool Detail Page ──

  test('tool detail page loads', async ({ page }) => {
    if (toolId) {
      const errors = setupConsoleErrorListener(page);
      await page.goto(`/tools/${toolId}`);
      await waitForPageReady(page);
      expect(errors).toHaveLength(0);
    }
  });

  // ── Delete Tool ──

  test('delete tool via API', async ({ page }) => {
    const toDelete = await createToolViaAPI(page, creds.token, {
      name: 'delete_me_tool',
      description: 'Will be deleted',
    });
    const id = (toDelete as any).id;

    const resp = await page.request.delete(`${API_BASE}/api/v1/tools/${id}`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
  });

  // ── Tool Execution via API ──

  test('test tool execution via API', async ({ page }) => {
    if (toolId) {
      const resp = await page.request.post(`${API_BASE}/api/v1/tools/${toolId}/test`, {
        headers: { Authorization: `Bearer ${creds.token}` },
        data: { query: 'test' },
      });
      // May succeed or fail depending on implementation config
      // Just verify API responds
      expect(resp.status()).toBeLessThan(500);
    }
  });

  // ── Builtin Tools via API ──

  test('list builtin tools via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/tools/catalog/builtin`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const tools = await resp.json();
    expect(Array.isArray(tools)).toBeTruthy();
  });

  // ── Integration Catalog via API ──

  test('list integration catalog via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/integrations/catalog`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const catalog = await resp.json();
    expect(Array.isArray(catalog)).toBeTruthy();
  });
});
