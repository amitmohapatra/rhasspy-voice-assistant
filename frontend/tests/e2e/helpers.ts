import { type Page, type BrowserContext, expect } from '@playwright/test';

/** Default API base for backend calls. */
export const API_BASE = process.env.API_URL || 'http://localhost:8000';

/**
 * Register + login via the API, set cookie + localStorage.
 * Returns credentials and token for reuse across tests.
 */
export async function registerAndLoginViaAPI(
  page: Page,
  baseURL: string
): Promise<{ email: string; password: string; token: string; name: string }> {
  const user = {
    email: `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@test.com`,
    password: 'TestPassword123!',
    name: 'E2E Test User',
  };

  // Register
  const regResp = await page.request.post(`${API_BASE}/api/v1/auth/register`, {
    data: { email: user.email, password: user.password, name: user.name },
  });
  expect(regResp.ok()).toBeTruthy();

  // Login
  const loginResp = await page.request.post(`${API_BASE}/api/v1/auth/login`, {
    data: { email: user.email, password: user.password },
  });
  expect(loginResp.ok()).toBeTruthy();
  const body = await loginResp.json();
  const token = body.access_token;

  // Set cookie for middleware
  await page.context().addCookies([
    {
      name: 'access_token',
      value: token,
      domain: new URL(baseURL).hostname,
      path: '/',
    },
  ]);

  // Set localStorage for api client
  await page.goto('/auth/login');
  await page.evaluate((t) => {
    localStorage.setItem('access_token', t);
  }, token);

  return { ...user, token };
}

/**
 * Inject auth token into page (cookie + localStorage).
 * Use when you already have a token from beforeAll.
 */
export async function injectAuth(
  page: Page,
  token: string,
  baseURL: string
): Promise<void> {
  await page.context().addCookies([
    {
      name: 'access_token',
      value: token,
      domain: new URL(baseURL).hostname,
      path: '/',
    },
  ]);
  await page.goto('/auth/login');
  await page.evaluate((t) => {
    localStorage.setItem('access_token', t);
  }, token);
}

/** Collect console errors from a page (ignoring known noise). */
export function setupConsoleErrorListener(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (
        text.includes('Failed to load resource') ||
        text.includes('net::ERR_') ||
        text.includes('hydration') ||
        text.includes('Warning:') ||
        text.includes('404')
      ) {
        return;
      }
      errors.push(text);
    }
  });
  return errors;
}

/**
 * Create an assistant via API. Returns the created assistant object.
 */
export async function createAssistantViaAPI(
  page: Page,
  token: string,
  data?: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const resp = await page.request.post(`${API_BASE}/api/v1/assistants`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Test Assistant ${Date.now()}`,
      system_prompt: 'You are a helpful assistant.',
      model: 'gpt-4o',
      provider: 'openai',
      ...data,
    },
  });
  expect(resp.ok()).toBeTruthy();
  return resp.json();
}

/**
 * Create a knowledge base via API. Returns the created KB object.
 */
export async function createKBViaAPI(
  page: Page,
  token: string,
  data?: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const resp = await page.request.post(`${API_BASE}/api/v1/knowledge-bases`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Test KB ${Date.now()}`,
      description: 'E2E test knowledge base',
      ...data,
    },
  });
  expect(resp.ok()).toBeTruthy();
  return resp.json();
}

/**
 * Create a custom tool via API. Returns the created tool object.
 */
export async function createToolViaAPI(
  page: Page,
  token: string,
  data?: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const resp = await page.request.post(`${API_BASE}/api/v1/tools/custom`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `test_tool_${Date.now()}`,
      description: 'E2E test tool',
      schema_definition: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Test param' },
        },
      },
      implementation: { type: 'http', method: 'GET', url: 'https://httpbin.org/get' },
      ...data,
    },
  });
  expect(resp.ok()).toBeTruthy();
  return resp.json();
}

/**
 * Create a project via API. Returns the created project object.
 */
export async function createProjectViaAPI(
  page: Page,
  token: string,
  data?: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const resp = await page.request.post(`${API_BASE}/api/v1/projects`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      name: `Test Project ${Date.now()}`,
      description: 'E2E test project',
      ...data,
    },
  });
  expect(resp.ok()).toBeTruthy();
  return resp.json();
}

/**
 * Upload a test file to a knowledge base via API.
 */
export async function uploadFileToKBViaAPI(
  page: Page,
  token: string,
  kbId: string,
  filename = 'test-document.txt',
  content = 'This is a test document for E2E testing of the RAG pipeline.'
): Promise<Record<string, unknown>> {
  const resp = await page.request.post(`${API_BASE}/api/v1/files/upload`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      file: {
        name: filename,
        mimeType: 'text/plain',
        buffer: Buffer.from(content),
      },
      knowledge_base_id: kbId,
    },
  });
  expect(resp.ok()).toBeTruthy();
  return resp.json();
}

/** Wait for page to be fully loaded (network idle + DOM stable). */
export async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(300); // let React hydrate
}
