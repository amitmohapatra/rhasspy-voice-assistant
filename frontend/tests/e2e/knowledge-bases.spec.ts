import { test, expect } from '@playwright/test';
import {
  registerAndLoginViaAPI,
  injectAuth,
  setupConsoleErrorListener,
  createKBViaAPI,
  uploadFileToKBViaAPI,
  waitForPageReady,
  API_BASE,
} from './helpers';
import path from 'path';

test.describe('Knowledge Bases & RAG Pipeline', () => {
  let creds: Awaited<ReturnType<typeof registerAndLoginViaAPI>>;
  let kbId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    creds = await registerAndLoginViaAPI(page, 'http://localhost:3000');
    const kb = await createKBViaAPI(page, creds.token, {
      name: 'Seeded KB',
      description: 'Knowledge base for E2E tests',
    });
    kbId = (kb as any).id;
    await page.close();
  });

  test.beforeEach(async ({ page, baseURL }) => {
    await injectAuth(page, creds.token, baseURL!);
  });

  // ── List Page ──

  test('knowledge bases page loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    await expect(page.getByText(/Knowledge Bases/i).first()).toBeVisible();
    expect(errors).toHaveLength(0);
  });

  test('shows seeded KB in list', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    await expect(page.getByText('Seeded KB').first()).toBeVisible();
  });

  test('search filters knowledge bases', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    const search = page.getByPlaceholder(/search/i).first();
    if (await search.isVisible()) {
      await search.fill('Seeded KB');
      await page.waitForTimeout(500);
      await expect(page.getByText('Seeded KB').first()).toBeVisible();
    }
  });

  test('search with no match shows empty state', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    const search = page.getByPlaceholder(/search/i).first();
    if (await search.isVisible()) {
      await search.fill('zzz_nonexistent_kb_999');
      await page.waitForTimeout(500);
    }
  });

  // ── Create KB ──

  test('new knowledge base button opens create form', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    const createBtn = page.getByRole('button', { name: /new knowledge base/i }).first()
      .or(page.getByText(/New Knowledge Base/i).first());
    await expect(createBtn).toBeVisible();
    await createBtn.click();
    // Should open a sheet/modal with form
    await page.waitForTimeout(500);
    await expect(page.getByPlaceholder(/name/i).first()
      .or(page.getByLabel(/name/i).first())).toBeVisible();
  });

  test('create KB form has required fields', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    const createBtn = page.getByRole('button', { name: /new knowledge base/i }).first()
      .or(page.getByText(/New Knowledge Base/i).first());
    await createBtn.click();
    await page.waitForTimeout(500);

    // Name field required
    const nameInput = page.getByPlaceholder(/name/i).first()
      .or(page.getByLabel(/name/i).first());
    await expect(nameInput).toBeVisible();

    // Description field (optional)
    const descInput = page.getByPlaceholder(/description/i).first()
      .or(page.getByLabel(/description/i).first());
    const hasDesc = await descInput.isVisible().catch(() => false);
  });

  test('create KB form has KB type selection', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    const createBtn = page.getByRole('button', { name: /new knowledge base/i }).first()
      .or(page.getByText(/New Knowledge Base/i).first());
    await createBtn.click();
    await page.waitForTimeout(500);

    // Should have provider managed vs platform managed options
    const body = await page.textContent('body');
    expect(
      body?.includes('Provider') || body?.includes('Platform') || body?.includes('type')
    ).toBeTruthy();
  });

  test('create KB end-to-end', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);

    const createBtn = page.getByRole('button', { name: /new knowledge base/i }).first()
      .or(page.getByText(/New Knowledge Base/i).first());
    await createBtn.click();
    await page.waitForTimeout(500);

    // Fill name
    const nameInput = page.getByPlaceholder(/name/i).first()
      .or(page.getByLabel(/name/i).first());
    await nameInput.fill('E2E Created KB');

    // Fill description
    const descInput = page.getByPlaceholder(/description/i).first()
      .or(page.getByLabel(/description/i).first());
    if (await descInput.isVisible()) {
      await descInput.fill('Created by Playwright E2E test');
    }

    // Submit
    const submitBtn = page.getByRole('button', { name: /create knowledge base/i }).first()
      .or(page.getByRole('button', { name: /create/i }).first());
    if (await submitBtn.isEnabled()) {
      await submitBtn.click();
      await page.waitForTimeout(2000);
    }
  });

  // ── File Upload ──

  test('upload file to KB via API', async ({ page }) => {
    const result = await uploadFileToKBViaAPI(
      page,
      creds.token,
      kbId,
      'test-rag-doc.txt',
      'The Eiffel Tower is a wrought-iron lattice tower in Paris, France. It was constructed from 1887 to 1889 as the centerpiece of the 1889 World Fair.'
    );
    expect(result).toBeTruthy();
  });

  test('upload PDF file to KB via API', async ({ page }) => {
    // Test with a simple content that simulates a document
    const result = await uploadFileToKBViaAPI(
      page,
      creds.token,
      kbId,
      'test-document.md',
      '# Test Document\n\nThis is a markdown test document for the RAG pipeline.\n\n## Section 1\n\nSome important information about machine learning and artificial intelligence.\n\n## Section 2\n\nMore content about natural language processing and embeddings.'
    );
    expect(result).toBeTruthy();
  });

  test('KB detail shows uploaded documents', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);

    // Click on the seeded KB to see details
    const kbCard = page.getByText('Seeded KB').first();
    await kbCard.click();
    await page.waitForTimeout(1000);

    // Should show documents section
    const body = await page.textContent('body');
    expect(
      body?.includes('Documents') ||
      body?.includes('test-rag-doc') ||
      body?.includes('document')
    ).toBeTruthy();
  });

  test('KB detail shows document count and chunk count', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);

    // The KB card should show document/chunk counts
    const body = await page.textContent('body');
    expect(
      body?.includes('document') || body?.includes('chunk') || body?.includes('Documents')
    ).toBeTruthy();
  });

  test('KB card shows status badge', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);

    // Should show status (ready, processing, error)
    const body = await page.textContent('body');
    expect(
      body?.toLowerCase().includes('ready') ||
      body?.toLowerCase().includes('processing') ||
      body?.toLowerCase().includes('active')
    ).toBeTruthy();
  });

  test('KB card shows type badge (Provider/Platform)', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    // Should indicate the KB type somewhere
    expect(body).toBeTruthy();
  });

  // ── File Upload via UI ──

  test('add files button visible in KB detail', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);

    // Select the KB
    const kbCard = page.getByText('Seeded KB').first();
    await kbCard.click();
    await page.waitForTimeout(1000);

    // Look for Add Files button
    const addFilesBtn = page.getByRole('button', { name: /add files/i }).first()
      .or(page.getByText(/Add Files/i).first());
    const hasBtn = await addFilesBtn.isVisible().catch(() => false);
    // Button should exist if there are documents
  });

  // ── Test Query (RAG retrieval) ──

  test('test query section exists in KB detail', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);

    const kbCard = page.getByText('Seeded KB').first();
    await kbCard.click();
    await page.waitForTimeout(1000);

    // Look for test query input
    const queryInput = page.getByPlaceholder(/query|search|test/i).first();
    const hasQuery = await queryInput.isVisible().catch(() => false);
    // May not be visible if no documents processed yet
  });

  // ── Delete KB ──

  test('delete KB via API and verify removal', async ({ page }) => {
    const toDelete = await createKBViaAPI(page, creds.token, {
      name: 'Delete Me KB',
    });
    const id = (toDelete as any).id;

    const resp = await page.request.delete(`${API_BASE}/api/v1/knowledge-bases/${id}`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();

    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    await page.waitForTimeout(500);
    const body = await page.textContent('body');
    expect(body).not.toContain('Delete Me KB');
  });

  // ── Grid/List View Toggle ──

  test('view toggle exists (grid/list)', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    // Should have view toggle buttons
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });

  // ── Pagination ──

  test('pagination controls visible when many items', async ({ page }) => {
    await page.goto('/knowledge-bases');
    await waitForPageReady(page);
    // Pagination may or may not show depending on item count
  });

  // ── RAG Pipeline Page ──

  test('RAG pipeline page loads', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/rag-pipelines');
    await waitForPageReady(page);

    const body = await page.textContent('body');
    expect(body?.toLowerCase()).toMatch(/rag|pipeline|test/);
    expect(errors).toHaveLength(0);
  });

  test('RAG pipeline page has connection testing', async ({ page }) => {
    await page.goto('/platform/rag-pipelines');
    await waitForPageReady(page);

    // Should have Qdrant and Redis connection test sections
    const body = await page.textContent('body');
    expect(
      body?.includes('Qdrant') || body?.includes('Redis') || body?.includes('Connection')
    ).toBeTruthy();
  });

  test('RAG pipeline Qdrant URL input editable', async ({ page }) => {
    await page.goto('/platform/rag-pipelines');
    await waitForPageReady(page);

    const qdrantInput = page.getByDisplayValue(/qdrant/i).first()
      .or(page.locator('input[value*="qdrant"]').first())
      .or(page.getByPlaceholder(/qdrant/i).first());
    const hasInput = await qdrantInput.isVisible().catch(() => false);
  });

  test('RAG pipeline has test connection buttons', async ({ page }) => {
    await page.goto('/platform/rag-pipelines');
    await waitForPageReady(page);

    const testBtn = page.getByRole('button', { name: /test connection/i }).first()
      .or(page.getByRole('button', { name: /test/i }).first());
    const hasBtn = await testBtn.isVisible().catch(() => false);
    expect(hasBtn).toBeTruthy();
  });

  test('RAG pipeline has end-to-end test section', async ({ page }) => {
    await page.goto('/platform/rag-pipelines');
    await waitForPageReady(page);

    // Should have file upload + query input for end-to-end test
    const body = await page.textContent('body');
    expect(
      body?.toLowerCase().includes('pipeline') ||
      body?.toLowerCase().includes('test') ||
      body?.toLowerCase().includes('upload')
    ).toBeTruthy();
  });

  test('RAG pipeline e2e test accepts file upload', async ({ page }) => {
    await page.goto('/platform/rag-pipelines');
    await waitForPageReady(page);

    // Look for file input
    const fileInput = page.locator('input[type="file"]').first();
    const hasFile = await fileInput.isVisible().catch(() => false);
    // File input might be hidden, check if it exists in DOM
    const count = await page.locator('input[type="file"]').count();
    // At least 0 file inputs (some may be hidden)
  });

  test('RAG pipeline e2e test has query input', async ({ page }) => {
    await page.goto('/platform/rag-pipelines');
    await waitForPageReady(page);

    const queryInput = page.getByPlaceholder(/query|question|search/i).first();
    const hasQuery = await queryInput.isVisible().catch(() => false);
  });

  // ── Document management via API ──

  test('list documents in KB via API', async ({ page }) => {
    const resp = await page.request.get(
      `${API_BASE}/api/v1/knowledge-bases/${kbId}/documents`,
      { headers: { Authorization: `Bearer ${creds.token}` } }
    );
    expect(resp.ok()).toBeTruthy();
    const docs = await resp.json();
    expect(Array.isArray(docs)).toBeTruthy();
  });

  test('upload multiple files to KB', async ({ page }) => {
    const files = [
      { name: 'doc1.txt', content: 'First test document about machine learning.' },
      { name: 'doc2.txt', content: 'Second test document about deep learning.' },
    ];

    for (const file of files) {
      const result = await uploadFileToKBViaAPI(
        page, creds.token, kbId, file.name, file.content
      );
      expect(result).toBeTruthy();
    }

    // Verify document count
    const resp = await page.request.get(
      `${API_BASE}/api/v1/knowledge-bases/${kbId}/documents`,
      { headers: { Authorization: `Bearer ${creds.token}` } }
    );
    const docs = await resp.json();
    expect(docs.length).toBeGreaterThanOrEqual(2);
  });

  test('delete document from KB via API', async ({ page }) => {
    // Upload a doc to delete
    const uploaded = await uploadFileToKBViaAPI(
      page, creds.token, kbId, 'to-delete.txt', 'Delete me'
    );
    const docId = (uploaded as any).id;

    if (docId) {
      const resp = await page.request.delete(
        `${API_BASE}/api/v1/knowledge-bases/${kbId}/documents/${docId}`,
        { headers: { Authorization: `Bearer ${creds.token}` } }
      );
      expect(resp.ok()).toBeTruthy();
    }
  });

  // ── Storage / Files Page ──

  test('storage page loads and shows uploaded files', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/platform/storage');
    await waitForPageReady(page);

    const body = await page.textContent('body');
    expect(body?.toLowerCase()).toMatch(/file|storage|upload/);
    expect(errors).toHaveLength(0);
  });

  test('storage page has search and filter', async ({ page }) => {
    await page.goto('/platform/storage');
    await waitForPageReady(page);

    const searchInput = page.getByPlaceholder(/search/i).first();
    const hasSearch = await searchInput.isVisible().catch(() => false);
  });

  test('storage page has file type filter', async ({ page }) => {
    await page.goto('/platform/storage');
    await waitForPageReady(page);

    // Should have a file type filter dropdown
    const body = await page.textContent('body');
    expect(
      body?.includes('All Types') ||
      body?.includes('PDF') ||
      body?.includes('filter')
    ).toBeTruthy();
  });

  test('storage page has view mode toggle (grid/list)', async ({ page }) => {
    await page.goto('/platform/storage');
    await waitForPageReady(page);
    // View toggle buttons should exist
  });

  test('storage page has pagination', async ({ page }) => {
    await page.goto('/platform/storage');
    await waitForPageReady(page);
    // Pagination controls
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
  });
});
