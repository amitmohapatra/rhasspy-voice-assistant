'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Play,
  Plus,
  Pencil,
  Trash2,
  Star,
  Mic,
  Volume2,
  Loader2,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  api,
  type VoicePreset,
  type VoicePresetListResponse,
  type VoiceProviderInfo,
  type AvailableVoiceProviders,
} from '@/lib/api';
import { useVoiceRecorder, blobToBase64 } from '@/hooks/use-voice-recorder';

const LANGUAGES = [
  { value: 'en-US', label: 'English (US)' },
  { value: 'en-GB', label: 'English (UK)' },
  { value: 'es-ES', label: 'Spanish (Spain)' },
  { value: 'es-MX', label: 'Spanish (Mexico)' },
  { value: 'fr-FR', label: 'French' },
  { value: 'de-DE', label: 'German' },
  { value: 'it-IT', label: 'Italian' },
  { value: 'pt-BR', label: 'Portuguese (Brazil)' },
  { value: 'ja-JP', label: 'Japanese' },
  { value: 'zh-CN', label: 'Chinese (Mandarin)' },
  { value: 'ko-KR', label: 'Korean' },
];

export default function VoicePage() {
  const [providers, setProviders] = useState<AvailableVoiceProviders | null>(null);
  const [ttsPresets, setTtsPresets] = useState<VoicePreset[]>([]);
  const [sttPresets, setSttPresets] = useState<VoicePreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'tts' | 'stt'>('tts');

  // TTS form state
  const [showTtsForm, setShowTtsForm] = useState(false);
  const [editingTtsId, setEditingTtsId] = useState<string | null>(null);
  const [ttsName, setTtsName] = useState('');
  const [ttsSource, setTtsSource] = useState('browser');
  const [ttsVoice, setTtsVoice] = useState('');
  const [ttsSpeed, setTtsSpeed] = useState(1.0);
  const [ttsPitch, setTtsPitch] = useState(1.0);
  const [ttsDefault, setTtsDefault] = useState(false);
  const [ttsSaving, setTtsSaving] = useState(false);
  const [ttsPreviewing, setTtsPreviewing] = useState(false);
  const [ttsPreviewText, setTtsPreviewText] = useState('Hello, this is a preview of the voice preset.');

  // STT form state
  const [showSttForm, setShowSttForm] = useState(false);
  const [editingSttId, setEditingSttId] = useState<string | null>(null);
  const [sttName, setSttName] = useState('');
  const [sttSource, setSttSource] = useState('browser');
  const [sttLanguage, setSttLanguage] = useState('en-US');
  const [sttDefault, setSttDefault] = useState(false);
  const [sttSaving, setSttSaving] = useState(false);
  const [sttTestResult, setSttTestResult] = useState<string | null>(null);
  const [sttTesting, setSttTesting] = useState(false);

  // Browser voices
  const [browserVoices, setBrowserVoices] = useState<SpeechSynthesisVoice[]>([]);

  const voiceRecorder = useVoiceRecorder();

  // Load browser voices
  useEffect(() => {
    const loadVoices = () => {
      const voices = window.speechSynthesis?.getVoices() || [];
      setBrowserVoices(voices);
    };
    loadVoices();
    window.speechSynthesis?.addEventListener('voiceschanged', loadVoices);
    return () => {
      window.speechSynthesis?.removeEventListener('voiceschanged', loadVoices);
    };
  }, []);

  const loadData = useCallback(async () => {
    try {
      const [providersData, ttsData, sttData] = await Promise.all([
        api.getAvailableVoiceProviders(),
        api.listVoicePresets('tts'),
        api.listVoicePresets('stt'),
      ]);
      setProviders(providersData);
      setTtsPresets(ttsData.items);
      setSttPresets(sttData.items);
    } catch (err) {
      console.error('Failed to load voice data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Available TTS/STT providers (only available: true)
  const availableTts = providers?.tts.filter((p) => p.available) || [];
  const availableStt = providers?.stt.filter((p) => p.available) || [];

  // Get voices for the selected TTS source
  const getVoicesForSource = (source: string): { value: string; label: string }[] => {
    if (source === 'browser') {
      return browserVoices.map((v) => ({ value: v.voiceURI, label: v.name }));
    }
    const provider = providers?.tts.find((p) => p.source === source);
    if (provider?.voices) {
      return provider.voices.map((v) => ({
        value: v,
        label: v.charAt(0).toUpperCase() + v.slice(1),
      }));
    }
    return [];
  };

  // TTS handlers
  const resetTtsForm = () => {
    setShowTtsForm(false);
    setEditingTtsId(null);
    setTtsName('');
    setTtsSource('browser');
    setTtsVoice('');
    setTtsSpeed(1.0);
    setTtsPitch(1.0);
    setTtsDefault(false);
  };

  const startEditTts = (preset: VoicePreset) => {
    setEditingTtsId(preset.id);
    setTtsName(preset.name);
    setTtsSource((preset.config.source as string) || 'browser');
    setTtsVoice((preset.config.voice_id as string) || (preset.config.voice_uri as string) || '');
    setTtsSpeed((preset.config.speed as number) || 1.0);
    setTtsPitch((preset.config.pitch as number) || 1.0);
    setTtsDefault(preset.is_default);
    setShowTtsForm(true);
  };

  const saveTtsPreset = async () => {
    if (!ttsName.trim()) return;
    setTtsSaving(true);
    try {
      const config: Record<string, unknown> = { source: ttsSource, speed: ttsSpeed };
      if (ttsSource === 'browser') {
        config.voice_uri = ttsVoice;
        config.voice_name = browserVoices.find((v) => v.voiceURI === ttsVoice)?.name || '';
        config.pitch = ttsPitch;
      } else {
        config.voice_id = ttsVoice;
      }

      if (editingTtsId) {
        await api.updateVoicePreset(editingTtsId, {
          name: ttsName,
          config,
          is_default: ttsDefault,
        });
      } else {
        await api.createVoicePreset({
          type: 'tts',
          name: ttsName,
          config,
          is_default: ttsDefault,
        });
      }
      resetTtsForm();
      await loadData();
    } catch (err) {
      console.error('Failed to save TTS preset:', err);
    } finally {
      setTtsSaving(false);
    }
  };

  const deleteTtsPreset = async (id: string) => {
    try {
      await api.deleteVoicePreset(id);
      await loadData();
    } catch (err) {
      console.error('Failed to delete preset:', err);
    }
  };

  const setTtsDefaultPreset = async (preset: VoicePreset) => {
    try {
      await api.updateVoicePreset(preset.id, { is_default: !preset.is_default });
      await loadData();
    } catch (err) {
      console.error('Failed to set default:', err);
    }
  };

  const previewTts = async () => {
    if (!ttsPreviewText.trim()) return;
    setTtsPreviewing(true);
    try {
      if (ttsSource === 'browser') {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(ttsPreviewText);
        const voice = browserVoices.find((v) => v.voiceURI === ttsVoice);
        if (voice) utterance.voice = voice;
        utterance.rate = ttsSpeed;
        utterance.pitch = ttsPitch;
        utterance.onend = () => setTtsPreviewing(false);
        utterance.onerror = () => setTtsPreviewing(false);
        window.speechSynthesis.speak(utterance);
      } else {
        const result = await api.synthesizeSpeech(ttsPreviewText, {
          voice_id: ttsVoice,
          provider: ttsSource,
          speaking_rate: ttsSpeed,
        });
        const audioBytes = Uint8Array.from(atob(result.audio), (c) => c.charCodeAt(0));
        const blob = new Blob([audioBytes], { type: `audio/${result.format}` });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.onended = () => {
          setTtsPreviewing(false);
          URL.revokeObjectURL(url);
        };
        audio.onerror = () => {
          setTtsPreviewing(false);
          URL.revokeObjectURL(url);
        };
        await audio.play();
      }
    } catch (err) {
      console.error('Preview failed:', err);
      setTtsPreviewing(false);
    }
  };

  // STT handlers
  const resetSttForm = () => {
    setShowSttForm(false);
    setEditingSttId(null);
    setSttName('');
    setSttSource('browser');
    setSttLanguage('en-US');
    setSttDefault(false);
    setSttTestResult(null);
  };

  const startEditStt = (preset: VoicePreset) => {
    setEditingSttId(preset.id);
    setSttName(preset.name);
    setSttSource((preset.config.source as string) || 'browser');
    setSttLanguage((preset.config.language as string) || 'en-US');
    setSttDefault(preset.is_default);
    setShowSttForm(true);
  };

  const saveSttPreset = async () => {
    if (!sttName.trim()) return;
    setSttSaving(true);
    try {
      const config: Record<string, unknown> = {
        source: sttSource,
        language: sttLanguage,
      };

      if (editingSttId) {
        await api.updateVoicePreset(editingSttId, {
          name: sttName,
          config,
          is_default: sttDefault,
        });
      } else {
        await api.createVoicePreset({
          type: 'stt',
          name: sttName,
          config,
          is_default: sttDefault,
        });
      }
      resetSttForm();
      await loadData();
    } catch (err) {
      console.error('Failed to save STT preset:', err);
    } finally {
      setSttSaving(false);
    }
  };

  const deleteSttPreset = async (id: string) => {
    try {
      await api.deleteVoicePreset(id);
      await loadData();
    } catch (err) {
      console.error('Failed to delete preset:', err);
    }
  };

  const setSttDefaultPreset = async (preset: VoicePreset) => {
    try {
      await api.updateVoicePreset(preset.id, { is_default: !preset.is_default });
      await loadData();
    } catch (err) {
      console.error('Failed to set default:', err);
    }
  };

  const testStt = async () => {
    setSttTesting(true);
    setSttTestResult(null);
    try {
      if (sttSource === 'browser') {
        const SpeechRecognitionAPI =
          (window as unknown as Record<string, unknown>).SpeechRecognition ||
          (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
        if (!SpeechRecognitionAPI) {
          setSttTestResult('Browser speech recognition not supported.');
          setSttTesting(false);
          return;
        }
        const recognition = new (SpeechRecognitionAPI as any)();
        recognition.lang = sttLanguage;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        recognition.onresult = (event: any) => {
          setSttTestResult(event.results[0][0].transcript);
          setSttTesting(false);
        };
        recognition.onerror = (event: any) => {
          setSttTestResult(`Error: ${event.error}`);
          setSttTesting(false);
        };
        recognition.onend = () => {
          setSttTesting(false);
        };
        recognition.start();
      } else {
        await voiceRecorder.startRecording();
        // Record for 3 seconds then stop
        setTimeout(async () => {
          const blob = await voiceRecorder.stopRecording();
          if (blob) {
            const base64 = await blobToBase64(blob);
            const result = await api.transcribeAudio(base64, {
              format: 'webm',
              language: sttLanguage,
            });
            setSttTestResult(result.text);
          }
          setSttTesting(false);
        }, 3000);
      }
    } catch (err) {
      console.error('STT test failed:', err);
      setSttTestResult('Test failed. Check console for details.');
      setSttTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Voice Settings</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Create and manage TTS and STT presets for use in avatar chat.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'tts' | 'stt')}>
        <TabsList>
          <TabsTrigger value="tts" className="gap-2">
            <Volume2 className="w-4 h-4" />
            Text-to-Speech
          </TabsTrigger>
          <TabsTrigger value="stt" className="gap-2">
            <Mic className="w-4 h-4" />
            Speech-to-Text
          </TabsTrigger>
        </TabsList>

        {/* TTS Tab */}
        <TabsContent value="tts">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {ttsPresets.length} preset{ttsPresets.length !== 1 ? 's' : ''}
              </p>
              <Button size="sm" onClick={() => { resetTtsForm(); setShowTtsForm(true); }}>
                <Plus className="w-4 h-4 mr-1" />
                New TTS Preset
              </Button>
            </div>

            {/* Preset List */}
            {ttsPresets.length === 0 && !showTtsForm ? (
              <div className="border border-dashed rounded-lg p-8 text-center text-muted-foreground">
                <Volume2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No TTS presets yet. Create one to get started.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {ttsPresets.map((preset) => (
                  <div
                    key={preset.id}
                    className="flex items-center justify-between p-3 border rounded-lg bg-card"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Volume2 className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm truncate">{preset.name}</span>
                          {preset.is_default && (
                            <Badge variant="secondary" className="text-[10px]">Default</Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {(preset.config.source as string) || 'browser'} &middot;{' '}
                          {(preset.config.voice_name as string) || (preset.config.voice_id as string) || 'default'} &middot;{' '}
                          speed {(preset.config.speed as number) || 1.0}x
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={() => setTtsDefaultPreset(preset)}
                        title={preset.is_default ? 'Remove default' : 'Set as default'}
                      >
                        <Star className={`w-4 h-4 ${preset.is_default ? 'fill-yellow-400 text-yellow-400' : ''}`} />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => startEditTts(preset)}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => deleteTtsPreset(preset.id)}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* TTS Create/Edit Form */}
            {showTtsForm && (
              <div className="border rounded-lg p-4 space-y-4 bg-card">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">
                    {editingTtsId ? 'Edit TTS Preset' : 'New TTS Preset'}
                  </h3>
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={resetTtsForm}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input
                      value={ttsName}
                      onChange={(e) => setTtsName(e.target.value)}
                      placeholder="e.g. Professional Nova"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Source</Label>
                    <Select value={ttsSource} onValueChange={(v) => { setTtsSource(v); setTtsVoice(''); }}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {availableTts.map((p) => (
                          <SelectItem key={p.source} value={p.source}>
                            {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Voice</Label>
                    <Select value={ttsVoice} onValueChange={setTtsVoice}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select voice" />
                      </SelectTrigger>
                      <SelectContent>
                        {getVoicesForSource(ttsSource).map((v) => (
                          <SelectItem key={v.value} value={v.value}>
                            {v.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Speed: {ttsSpeed.toFixed(1)}x</Label>
                    <Slider
                      min={0.5}
                      max={2.0}
                      step={0.1}
                      value={[ttsSpeed]}
                      onValueChange={([v]) => setTtsSpeed(v)}
                    />
                  </div>

                  {ttsSource === 'browser' && (
                    <div className="space-y-2">
                      <Label>Pitch: {ttsPitch.toFixed(1)}</Label>
                      <Slider
                        min={0.5}
                        max={2.0}
                        step={0.1}
                        value={[ttsPitch]}
                        onValueChange={([v]) => setTtsPitch(v)}
                      />
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="tts-default"
                      checked={ttsDefault}
                      onChange={(e) => setTtsDefault(e.target.checked)}
                      className="rounded"
                    />
                    <Label htmlFor="tts-default">Set as default</Label>
                  </div>
                </div>

                {/* Preview */}
                <div className="space-y-2">
                  <Label>Preview</Label>
                  <div className="flex gap-2">
                    <Input
                      value={ttsPreviewText}
                      onChange={(e) => setTtsPreviewText(e.target.value)}
                      placeholder="Preview text..."
                      className="flex-1"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={previewTts}
                      disabled={ttsPreviewing}
                    >
                      {ttsPreviewing ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Play className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={resetTtsForm}>
                    Cancel
                  </Button>
                  <Button onClick={saveTtsPreset} disabled={ttsSaving || !ttsName.trim()}>
                    {ttsSaving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                    {editingTtsId ? 'Update Preset' : 'Save Preset'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </TabsContent>

        {/* STT Tab */}
        <TabsContent value="stt">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {sttPresets.length} preset{sttPresets.length !== 1 ? 's' : ''}
              </p>
              <Button size="sm" onClick={() => { resetSttForm(); setShowSttForm(true); }}>
                <Plus className="w-4 h-4 mr-1" />
                New STT Preset
              </Button>
            </div>

            {/* Preset List */}
            {sttPresets.length === 0 && !showSttForm ? (
              <div className="border border-dashed rounded-lg p-8 text-center text-muted-foreground">
                <Mic className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No STT presets yet. Create one to get started.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {sttPresets.map((preset) => (
                  <div
                    key={preset.id}
                    className="flex items-center justify-between p-3 border rounded-lg bg-card"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Mic className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm truncate">{preset.name}</span>
                          {preset.is_default && (
                            <Badge variant="secondary" className="text-[10px]">Default</Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {(preset.config.source as string) || 'browser'} &middot;{' '}
                          {(preset.config.language as string) || 'en-US'}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={() => setSttDefaultPreset(preset)}
                        title={preset.is_default ? 'Remove default' : 'Set as default'}
                      >
                        <Star className={`w-4 h-4 ${preset.is_default ? 'fill-yellow-400 text-yellow-400' : ''}`} />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => startEditStt(preset)}>
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => deleteSttPreset(preset.id)}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* STT Create/Edit Form */}
            {showSttForm && (
              <div className="border rounded-lg p-4 space-y-4 bg-card">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">
                    {editingSttId ? 'Edit STT Preset' : 'New STT Preset'}
                  </h3>
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={resetSttForm}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input
                      value={sttName}
                      onChange={(e) => setSttName(e.target.value)}
                      placeholder="e.g. Whisper EN"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Source</Label>
                    <Select value={sttSource} onValueChange={setSttSource}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {availableStt.map((p) => (
                          <SelectItem key={p.source} value={p.source}>
                            {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Language</Label>
                    <Select value={sttLanguage} onValueChange={setSttLanguage}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {LANGUAGES.map((lang) => (
                          <SelectItem key={lang.value} value={lang.value}>
                            {lang.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="stt-default"
                      checked={sttDefault}
                      onChange={(e) => setSttDefault(e.target.checked)}
                      className="rounded"
                    />
                    <Label htmlFor="stt-default">Set as default</Label>
                  </div>
                </div>

                {/* Test */}
                <div className="space-y-2">
                  <Label>Test</Label>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={testStt}
                      disabled={sttTesting}
                    >
                      {sttTesting ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-1" />
                      ) : (
                        <Mic className="w-4 h-4 mr-1" />
                      )}
                      {sttTesting ? 'Listening...' : 'Record & Transcribe'}
                    </Button>
                    {sttTestResult && (
                      <p className="text-sm text-muted-foreground flex-1 truncate">
                        Result: &ldquo;{sttTestResult}&rdquo;
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={resetSttForm}>
                    Cancel
                  </Button>
                  <Button onClick={saveSttPreset} disabled={sttSaving || !sttName.trim()}>
                    {sttSaving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                    {editingSttId ? 'Update Preset' : 'Save Preset'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
