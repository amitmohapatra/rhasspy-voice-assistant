'use client';

import { useState, useRef } from 'react';
import { Mic, Volume2, Upload, Play, Pause, Download, Loader2, StopCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const voices = [
  { id: 'alloy', name: 'Alloy', description: 'Neutral and balanced' },
  { id: 'echo', name: 'Echo', description: 'Warm and conversational' },
  { id: 'fable', name: 'Fable', description: 'Expressive and dynamic' },
  { id: 'nova', name: 'Nova', description: 'Friendly and upbeat' },
  { id: 'onyx', name: 'Onyx', description: 'Deep and authoritative' },
  { id: 'shimmer', name: 'Shimmer', description: 'Clear and engaging' },
];

export default function AudioPage() {
  const [activeTab, setActiveTab] = useState('tts');
  const [ttsText, setTtsText] = useState('');
  const [selectedVoice, setSelectedVoice] = useState('nova');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [transcription, setTranscription] = useState('');
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleGenerateSpeech = async () => {
    if (!ttsText.trim()) return;
    setIsGenerating(true);
    // Simulate API call
    setTimeout(() => {
      setIsGenerating(false);
      setAudioUrl('/sample-audio.mp3');
    }, 2000);
  };

  const handleStartRecording = () => {
    setIsRecording(true);
    // In real implementation, start recording
  };

  const handleStopRecording = () => {
    setIsRecording(false);
    // Simulate transcription
    setTranscription('This is a sample transcription from speech-to-text.');
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Simulate file upload and transcription
      setTranscription('Transcription from uploaded audio file...');
    }
  };

  return (
    <div className="flex-1 p-6 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Mic className="w-6 h-6" />
            Audio
          </h1>
          <p className="text-muted-foreground mt-1">
            Speech-to-text and text-to-speech capabilities
          </p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-2 max-w-md">
            <TabsTrigger value="tts" className="flex items-center gap-2">
              <Volume2 className="w-4 h-4" />
              Text to Speech
            </TabsTrigger>
            <TabsTrigger value="stt" className="flex items-center gap-2">
              <Mic className="w-4 h-4" />
              Speech to Text
            </TabsTrigger>
          </TabsList>

          <TabsContent value="tts" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Generate Speech</CardTitle>
                <CardDescription>Convert text to natural-sounding speech</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Voice</Label>
                  <Select value={selectedVoice} onValueChange={setSelectedVoice}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {voices.map((voice) => (
                        <SelectItem key={voice.id} value={voice.id}>
                          <div>
                            <span className="font-medium">{voice.name}</span>
                            <span className="text-muted-foreground ml-2 text-sm">
                              - {voice.description}
                            </span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Text</Label>
                  <Textarea
                    value={ttsText}
                    onChange={(e) => setTtsText(e.target.value)}
                    placeholder="Enter text to convert to speech..."
                    rows={6}
                  />
                  <p className="text-xs text-muted-foreground text-right">
                    {ttsText.length} / 4096 characters
                  </p>
                </div>

                <Button
                  onClick={handleGenerateSpeech}
                  disabled={!ttsText.trim() || isGenerating}
                  className="w-full"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-4 h-4 mr-2" />
                      Generate Speech
                    </>
                  )}
                </Button>

                {audioUrl && (
                  <div className="p-4 bg-muted rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Button variant="outline" size="icon">
                          <Play className="w-4 h-4" />
                        </Button>
                        <div className="flex-1 h-2 bg-primary/20 rounded-full">
                          <div className="w-1/3 h-full bg-primary rounded-full" />
                        </div>
                        <span className="text-sm text-muted-foreground">0:00 / 0:15</span>
                      </div>
                      <Button variant="ghost" size="icon">
                        <Download className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="stt" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Transcribe Audio</CardTitle>
                <CardDescription>Convert speech to text</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <Button
                    variant={isRecording ? 'destructive' : 'outline'}
                    className="h-24"
                    onClick={isRecording ? handleStopRecording : handleStartRecording}
                  >
                    {isRecording ? (
                      <div className="text-center">
                        <StopCircle className="w-8 h-8 mx-auto mb-2 animate-pulse" />
                        <span>Stop Recording</span>
                      </div>
                    ) : (
                      <div className="text-center">
                        <Mic className="w-8 h-8 mx-auto mb-2" />
                        <span>Start Recording</span>
                      </div>
                    )}
                  </Button>

                  <Button
                    variant="outline"
                    className="h-24"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <div className="text-center">
                      <Upload className="w-8 h-8 mx-auto mb-2" />
                      <span>Upload Audio</span>
                    </div>
                  </Button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="audio/*"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </div>

                {transcription && (
                  <div className="space-y-2">
                    <Label>Transcription</Label>
                    <div className="p-4 bg-muted rounded-lg min-h-[100px]">
                      <p className="text-sm">{transcription}</p>
                    </div>
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm">
                        Copy
                      </Button>
                      <Button variant="outline" size="sm">
                        Download
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
