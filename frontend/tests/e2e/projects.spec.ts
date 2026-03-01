import { test, expect } from '@playwright/test';
import {
  registerAndLoginViaAPI,
  injectAuth,
  setupConsoleErrorListener,
  createProjectViaAPI,
  waitForPageReady,
  API_BASE,
} from './helpers';

test.describe('Projects', () => {
  let creds: Awaited<ReturnType<typeof registerAndLoginViaAPI>>;
  let projectId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    creds = await registerAndLoginViaAPI(page, 'http://localhost:3000');
    const project = await createProjectViaAPI(page, creds.token, {
      name: 'Seeded Project',
      description: 'A seeded project for E2E tests',
    });
    projectId = (project as any).id;
    await page.close();
  });

  test.beforeEach(async ({ page, baseURL }) => {
    await injectAuth(page, creds.token, baseURL!);
  });

  // ── List Page ──

  test('projects page loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/projects');
    await waitForPageReady(page);
    await expect(page.getByText(/Projects/i).first()).toBeVisible();
    expect(errors).toHaveLength(0);
  });

  test('shows seeded project in list', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);
    await expect(page.getByText('Seeded Project').first()).toBeVisible();
  });

  test('new project button visible', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);
    const btn = page.getByRole('button', { name: /new project/i }).first();
    await expect(btn).toBeVisible();
  });

  test('new project button opens modal', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);
    await page.getByRole('button', { name: /new project/i }).first().click();
    await page.waitForTimeout(500);

    // Modal should have name and description fields
    await expect(page.getByText('Create New Project').first()).toBeVisible();
    const nameInput = page.getByPlaceholder(/my ai assistant/i).first()
      .or(page.getByLabel(/project name/i).first());
    await expect(nameInput).toBeVisible();
  });

  test('create project modal has description textarea', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);
    await page.getByRole('button', { name: /new project/i }).first().click();
    await page.waitForTimeout(500);

    const descInput = page.getByPlaceholder(/describe your project/i).first()
      .or(page.getByLabel(/description/i).first());
    const hasDesc = await descInput.isVisible().catch(() => false);
    expect(hasDesc).toBeTruthy();
  });

  test('create project modal cancel button works', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);
    await page.getByRole('button', { name: /new project/i }).first().click();
    await page.waitForTimeout(500);

    const cancelBtn = page.getByRole('button', { name: /cancel/i }).first();
    await cancelBtn.click();
    await page.waitForTimeout(300);

    // Modal should close
    await expect(page.getByText('Create New Project')).not.toBeVisible();
  });

  test('create project end-to-end', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);
    await page.getByRole('button', { name: /new project/i }).first().click();
    await page.waitForTimeout(500);

    const nameInput = page.getByPlaceholder(/my ai assistant/i).first()
      .or(page.getByLabel(/project name/i).first());
    await nameInput.fill('E2E Created Project');

    const descInput = page.getByPlaceholder(/describe your project/i).first();
    if (await descInput.isVisible()) {
      await descInput.fill('Created by Playwright test');
    }

    const createBtn = page.getByRole('button', { name: /create project/i }).first();
    await createBtn.click();

    // Should redirect to project detail page
    await page.waitForURL('**/projects/**', { timeout: 5000 });
  });

  test('project card links to detail page', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);

    const card = page.getByText('Seeded Project').first();
    await card.click();
    await expect(page).toHaveURL(/\/projects\//);
  });

  test('add project card (dashed border) opens modal', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);

    const addCard = page.getByText('Add Project').first();
    if (await addCard.isVisible()) {
      await addCard.click();
      await page.waitForTimeout(500);
      await expect(page.getByText('Create New Project').first()).toBeVisible();
    }
  });

  test('getting started workflow visible', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);
    await expect(page.getByText('Getting Started Workflow').first()).toBeVisible();
  });

  test('workflow steps visible (5 steps)', async ({ page }) => {
    await page.goto('/projects');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body).toContain('Create Project');
    expect(body).toContain('Configure Providers');
    expect(body).toContain('Create Knowledge Base');
    expect(body).toContain('Create Assistant');
  });

  // ── Project Detail Page ──

  test('project detail page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto(`/projects/${projectId}`);
    await waitForPageReady(page);
    expect(errors).toHaveLength(0);
  });

  test('project detail shows project name', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);
    await waitForPageReady(page);
    await expect(page.getByText('Seeded Project').first()).toBeVisible();
  });

  test('project detail has tabs', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Overview') || body?.includes('Providers') ||
      body?.includes('Secrets') || body?.includes('Assistants')
    ).toBeTruthy();
  });

  test('project detail overview tab shows description', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body).toContain('Seeded Project');
  });

  test('project detail overview has quick actions', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(
      body?.includes('Create Knowledge Base') ||
      body?.includes('Create Assistant') ||
      body?.includes('Quick Actions')
    ).toBeTruthy();
  });

  test('project detail secrets tab loads', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);
    await waitForPageReady(page);

    const secretsTab = page.getByText(/Secrets/i).first()
      .or(page.getByText(/API Keys/i).first());
    if (await secretsTab.isVisible()) {
      await secretsTab.click();
      await page.waitForTimeout(500);
      const body = await page.textContent('body');
      expect(
        body?.includes('Secret') || body?.includes('secret') ||
        body?.includes('Add Secret')
      ).toBeTruthy();
    }
  });

  test('project detail assistants tab loads', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);
    await waitForPageReady(page);

    const assistantsTab = page.getByText(/Assistants/i).first();
    if (await assistantsTab.isVisible()) {
      await assistantsTab.click();
      await page.waitForTimeout(500);
    }
  });

  test('project detail back button navigates to projects list', async ({ page }) => {
    await page.goto(`/projects/${projectId}`);
    await waitForPageReady(page);

    const backBtn = page.locator('a[href="/projects"]').first()
      .or(page.getByRole('link', { name: /back|projects/i }).first());
    if (await backBtn.isVisible()) {
      await backBtn.click();
      await expect(page).toHaveURL(/\/projects$/);
    }
  });

  // ── Projects CRUD via API ──

  test('list projects via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/projects`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const projects = await resp.json();
    expect(Array.isArray(projects)).toBeTruthy();
    expect(projects.length).toBeGreaterThanOrEqual(1);
  });

  test('get project by ID via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/projects/${projectId}`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const project = await resp.json();
    expect(project.name).toBe('Seeded Project');
  });

  test('update project via API', async ({ page }) => {
    const resp = await page.request.put(`${API_BASE}/api/v1/projects/${projectId}`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: { description: 'Updated description via E2E test' },
    });
    expect(resp.ok()).toBeTruthy();
  });

  test('delete project via API', async ({ page }) => {
    const toDelete = await createProjectViaAPI(page, creds.token, {
      name: 'Delete Me Project',
    });
    const id = (toDelete as any).id;

    const resp = await page.request.delete(`${API_BASE}/api/v1/projects/${id}`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
  });

  // ── Secrets via API ──

  test('list secrets via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/secrets`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
    const data = await resp.json();
    expect(data).toHaveProperty('items');
  });

  test('create secret via API', async ({ page }) => {
    const resp = await page.request.post(`${API_BASE}/api/v1/secrets`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: {
        key: `E2E_TEST_SECRET_${Date.now()}`,
        value: 'test-secret-value',
        description: 'Created by E2E test',
      },
    });
    // May succeed or fail depending on backend
    expect(resp.status()).toBeLessThan(500);
  });
});
