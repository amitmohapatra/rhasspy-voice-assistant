'use client';

import { useState, useRef, useCallback, useEffect } from 'react';

export type RecordingState = 'idle' | 'recording' | 'processing';

interface VoiceRecorderOptions {
  sampleRate?: number;
  channelCount?: number;
  mimeType?: string;
  onAudioLevel?: (level: number) => void;
}

interface VoiceRecorderReturn {
  state: RecordingState;
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<Blob | null>;
  cancelRecording: () => void;
  audioLevel: number;
  duration: number;
  error: string | null;
}

export function useVoiceRecorder(options: VoiceRecorderOptions = {}): VoiceRecorderReturn {
  const {
    sampleRate = 16000,
    channelCount = 1,
    mimeType = 'audio/webm;codecs=opus',
    onAudioLevel,
  } = options;

  const [state, setState] = useState<RecordingState>('idle');
  const [audioLevel, setAudioLevel] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const animationFrameRef = useRef<number | null>(null);
  const durationIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Cleanup function
  const cleanup = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current);
      durationIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    mediaRecorderRef.current = null;
    analyserRef.current = null;
    chunksRef.current = [];
    setAudioLevel(0);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  // Audio level monitoring
  const monitorAudioLevel = useCallback(() => {
    if (!analyserRef.current) return;

    const analyser = analyserRef.current;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const updateLevel = () => {
      if (state !== 'recording') return;

      analyser.getByteFrequencyData(dataArray);

      // Calculate RMS
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i] * dataArray[i];
      }
      const rms = Math.sqrt(sum / dataArray.length);
      const level = Math.min(1, rms / 128); // Normalize to 0-1

      setAudioLevel(level);
      onAudioLevel?.(level);

      animationFrameRef.current = requestAnimationFrame(updateLevel);
    };

    updateLevel();
  }, [state, onAudioLevel]);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      cleanup();

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate,
          channelCount,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // Set up audio context for level monitoring
      audioContextRef.current = new AudioContext({ sampleRate });
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      source.connect(analyserRef.current);

      // Determine best supported MIME type
      let selectedMimeType = mimeType;
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        const alternatives = [
          'audio/webm;codecs=opus',
          'audio/webm',
          'audio/ogg;codecs=opus',
          'audio/mp4',
          '',
        ];
        selectedMimeType = alternatives.find((type) =>
          type === '' || MediaRecorder.isTypeSupported(type)
        ) || '';
      }

      // Set up MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: selectedMimeType || undefined,
        audioBitsPerSecond: 128000,
      });
      mediaRecorderRef.current = mediaRecorder;

      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event);
        setError('Recording error occurred');
        cleanup();
        setState('idle');
      };

      // Start recording
      mediaRecorder.start(100); // Collect data every 100ms
      startTimeRef.current = Date.now();
      setState('recording');

      // Start duration counter
      durationIntervalRef.current = setInterval(() => {
        setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000));
      }, 1000);

      // Start audio level monitoring
      monitorAudioLevel();
    } catch (err) {
      console.error('Failed to start recording:', err);
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to access microphone. Please check permissions.'
      );
      cleanup();
      setState('idle');
    }
  }, [sampleRate, channelCount, mimeType, cleanup, monitorAudioLevel]);

  const stopRecording = useCallback(async (): Promise<Blob | null> => {
    return new Promise((resolve) => {
      if (!mediaRecorderRef.current || state !== 'recording') {
        resolve(null);
        return;
      }

      setState('processing');

      const mediaRecorder = mediaRecorderRef.current;

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: mediaRecorder.mimeType || 'audio/webm',
        });
        cleanup();
        setState('idle');
        setDuration(0);
        resolve(blob);
      };

      mediaRecorder.stop();
    });
  }, [state, cleanup]);

  const cancelRecording = useCallback(() => {
    cleanup();
    setState('idle');
    setDuration(0);
  }, [cleanup]);

  return {
    state,
    isRecording: state === 'recording',
    startRecording,
    stopRecording,
    cancelRecording,
    audioLevel,
    duration,
    error,
  };
}

/**
 * Format seconds as mm:ss
 */
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Convert audio Blob to base64
 */
export async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result as string;
      // Remove data URL prefix
      const base64Data = base64.split(',')[1];
      resolve(base64Data);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

/**
 * Convert audio Blob to ArrayBuffer for WAV conversion
 */
export async function blobToArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  return blob.arrayBuffer();
}
