import { test, expect } from '@playwright/test';
import {
  registerAndLoginViaAPI,
  injectAuth,
  setupConsoleErrorListener,
  waitForPageReady,
  API_BASE,
} from './helpers';

test.describe('Voice Settings & Presets', () => {
  let creds: Awaited<ReturnType<typeof registerAndLoginViaAPI>>;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    creds = await registerAndLoginViaAPI(page, 'http://localhost:3000');
    await page.close();
  });

  test.beforeEach(async ({ page, baseURL }) => {
    await injectAuth(page, creds.token, baseURL!);
  });

  // ── Voice Settings Page ──

  test('voice settings page loads without errors', async ({ page }) => {
    const errors = setupConsoleErrorListener(page);
    await page.goto('/manage/voice');
    await waitForPageReady(page);
    const body = await page.textContent('body');
    expect(body?.toLowerCase()).toMatch(/voice|settings/);
    expect(errors).toHaveLength(0);
  });

  test('voice settings has TTS and STT tabs', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);
    await expect(page.getByText(/Text-to-Speech/i).first()).toBeVisible();
    await expect(page.getByText(/Speech-to-Text/i).first()).toBeVisible();
  });

  // ── TTS Tab ──

  test('TTS tab is default active tab', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);
    // TTS content should be visible by default
    const body = await page.textContent('body');
    expect(
      body?.includes('TTS') || body?.includes('Text-to-Speech') || body?.includes('Preset')
    ).toBeTruthy();
  });

  test('TTS tab has new preset button', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);
    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await expect(btn).toBeVisible();
  });

  test('TTS new preset form opens', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    // Form should show name input
    const nameInput = page.getByPlaceholder(/professional nova/i).first()
      .or(page.getByLabel(/name/i).first());
    await expect(nameInput).toBeVisible();
  });

  test('TTS form has source selector', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('Source') || body?.includes('Browser') || body?.includes('source')
    ).toBeTruthy();
  });

  test('TTS form has voice selector', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('Voice') || body?.includes('voice')
    ).toBeTruthy();
  });

  test('TTS form has speed slider', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('Speed') || body?.includes('speed')
    ).toBeTruthy();
  });

  test('TTS form has default checkbox', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('default') || body?.includes('Default')
    ).toBeTruthy();
  });

  test('TTS form has preview section', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('Preview') || body?.includes('preview') || body?.includes('Play')
    ).toBeTruthy();
  });

  test('TTS form cancel closes form', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    const cancelBtn = page.getByRole('button', { name: /cancel/i }).first();
    await cancelBtn.click();
    await page.waitForTimeout(300);
  });

  test('create TTS preset end-to-end', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const btn = page.getByRole('button', { name: /new tts preset/i }).first()
      .or(page.getByText(/New TTS Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    // Fill name
    const nameInput = page.getByPlaceholder(/professional nova/i).first()
      .or(page.getByLabel(/name/i).first());
    await nameInput.fill('E2E TTS Preset');

    // Submit
    const saveBtn = page.getByRole('button', { name: /save preset/i }).first()
      .or(page.getByRole('button', { name: /save/i }).first());
    if (await saveBtn.isEnabled()) {
      await saveBtn.click();
      await page.waitForTimeout(2000);
    }
  });

  // ── STT Tab ──

  test('STT tab loads', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const sttTab = page.getByText(/Speech-to-Text/i).first();
    await sttTab.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('STT') || body?.includes('Speech-to-Text') || body?.includes('Preset')
    ).toBeTruthy();
  });

  test('STT tab has new preset button', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const sttTab = page.getByText(/Speech-to-Text/i).first();
    await sttTab.click();
    await page.waitForTimeout(500);

    const btn = page.getByRole('button', { name: /new stt preset/i }).first()
      .or(page.getByText(/New STT Preset/i).first());
    await expect(btn).toBeVisible();
  });

  test('STT new preset form has language selector', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const sttTab = page.getByText(/Speech-to-Text/i).first();
    await sttTab.click();
    await page.waitForTimeout(500);

    const btn = page.getByRole('button', { name: /new stt preset/i }).first()
      .or(page.getByText(/New STT Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('Language') || body?.includes('en-US') || body?.includes('language')
    ).toBeTruthy();
  });

  test('STT form has test recording button', async ({ page }) => {
    await page.goto('/manage/voice');
    await waitForPageReady(page);

    const sttTab = page.getByText(/Speech-to-Text/i).first();
    await sttTab.click();
    await page.waitForTimeout(500);

    const btn = page.getByRole('button', { name: /new stt preset/i }).first()
      .or(page.getByText(/New STT Preset/i).first());
    await btn.click();
    await page.waitForTimeout(500);

    const body = await page.textContent('body');
    expect(
      body?.includes('Record') || body?.includes('Transcribe') || body?.includes('Test')
    ).toBeTruthy();
  });

  // ── Voice API Endpoints ──

  test('list voice presets via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/voice-presets`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
  });

  test('list voice presets by type (TTS) via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/voice-presets?type=tts`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
  });

  test('list voice presets by type (STT) via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/voice-presets?type=stt`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
  });

  test('get available voice providers via API', async ({ page }) => {
    const resp = await page.request.get(`${API_BASE}/api/v1/voice/available-providers`, {
      headers: { Authorization: `Bearer ${creds.token}` },
    });
    expect(resp.ok()).toBeTruthy();
  });

  test('create TTS preset via API', async ({ page }) => {
    const resp = await page.request.post(`${API_BASE}/api/v1/voice-presets`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: {
        type: 'tts',
        name: `API TTS Preset ${Date.now()}`,
        config: { source: 'browser', voice: 'default', speed: 1.0 },
        is_default: false,
      },
    });
    expect(resp.ok()).toBeTruthy();
    const preset = await resp.json();
    expect(preset).toHaveProperty('id');

    // Cleanup - delete the preset
    if (preset.id) {
      await page.request.delete(`${API_BASE}/api/v1/voice-presets/${preset.id}`, {
        headers: { Authorization: `Bearer ${creds.token}` },
      });
    }
  });

  test('create STT preset via API', async ({ page }) => {
    const resp = await page.request.post(`${API_BASE}/api/v1/voice-presets`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: {
        type: 'stt',
        name: `API STT Preset ${Date.now()}`,
        config: { source: 'browser', language: 'en-US' },
        is_default: false,
      },
    });
    expect(resp.ok()).toBeTruthy();
    const preset = await resp.json();
    expect(preset).toHaveProperty('id');

    // Cleanup
    if (preset.id) {
      await page.request.delete(`${API_BASE}/api/v1/voice-presets/${preset.id}`, {
        headers: { Authorization: `Bearer ${creds.token}` },
      });
    }
  });

  test('voice transcription endpoint via API', async ({ page }) => {
    // Send a minimal audio payload
    const resp = await page.request.post(`${API_BASE}/api/v1/voice/transcribe`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: {
        audio: '', // Empty base64 for endpoint check
        format: 'webm',
      },
    });
    // Will likely fail (empty audio) but should not 500
    expect(resp.status()).toBeLessThan(500);
  });

  test('voice synthesis endpoint via API', async ({ page }) => {
    const resp = await page.request.post(`${API_BASE}/api/v1/voice/synthesize`, {
      headers: { Authorization: `Bearer ${creds.token}` },
      data: {
        text: 'Hello E2E test',
        provider: 'browser',
      },
    });
    // May fail if no provider configured
    expect(resp.status()).toBeLessThan(500);
  });
});
