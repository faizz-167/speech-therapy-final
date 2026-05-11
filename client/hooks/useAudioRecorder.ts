"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import type { RecordingMeta } from "@/types";

// ---------------------------------------------------------------------------
// Speech onset detection threshold (RMS amplitude, 0–1 scale)
// ---------------------------------------------------------------------------

const SPEECH_ONSET_RMS = 0.06;

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------

export interface AudioRecorderState {
  recording: boolean;
  captured: boolean;
  micError: string | null;
  elapsed: number;
  previewUrl: string | null;
  start: () => Promise<void>;
  stop: () => void;
  reRecord: () => void;
  submit: () => void;
}

// ---------------------------------------------------------------------------
// useAudioRecorder
// ---------------------------------------------------------------------------

export function useAudioRecorder(
  onComplete: (blob: Blob, meta: RecordingMeta) => void,
): AudioRecorderState {
  const [recording, setRecording] = useState(false);
  const [captured, setCaptured] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const micActivatedAtRef = useRef<string | null>(null);
  const speechStartAtRef = useRef<string | null>(null);
  const blobRef = useRef<Blob | null>(null);
  const metaRef = useRef<RecordingMeta | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stable reference to the latest onComplete callback
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  function stopLevelTracking() {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    analyserRef.current?.disconnect();
    analyserRef.current = null;
    if (audioContextRef.current) {
      void audioContextRef.current.close();
      audioContextRef.current = null;
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopLevelTracking();
      if (timerRef.current) clearInterval(timerRef.current);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = useCallback(async () => {
    setMicError(null);
    setElapsed(0);

    const stream = await navigator.mediaDevices
      .getUserMedia({ audio: true })
      .catch(() => null);

    if (!stream) {
      setMicError(
        "Microphone access denied. Please allow microphone permission and try again.",
      );
      return;
    }

    const mr = new MediaRecorder(stream);
    const activatedAt = new Date().toISOString();
    micActivatedAtRef.current = activatedAt;
    speechStartAtRef.current = null;
    chunksRef.current = [];
    blobRef.current = null;
    metaRef.current = null;

    mr.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    mr.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      stopLevelTracking();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      blobRef.current = blob;
      const url = URL.createObjectURL(blob);
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return url;
      });
      metaRef.current = {
        micActivatedAt: micActivatedAtRef.current ?? activatedAt,
        speechStartAt: speechStartAtRef.current,
      };
      setCaptured(true);
      stream.getTracks().forEach((t) => t.stop());
    };

    // Speech onset detection via AudioContext analyser
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);
    audioContextRef.current = audioContext;
    analyserRef.current = analyser;

    const data = new Uint8Array(analyser.frequencyBinCount);
    const monitorSpeech = () => {
      if (!analyserRef.current) return;
      analyserRef.current.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (const value of data) {
        const centered = (value - 128) / 128;
        sumSquares += centered * centered;
      }
      const rms = Math.sqrt(sumSquares / data.length);
      if (!speechStartAtRef.current && rms > SPEECH_ONSET_RMS) {
        speechStartAtRef.current = new Date().toISOString();
      }
      animationFrameRef.current = requestAnimationFrame(monitorSpeech);
    };
    animationFrameRef.current = requestAnimationFrame(monitorSpeech);

    mr.start();
    mediaRef.current = mr;
    setRecording(true);
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
  }, []);

  const stop = useCallback(() => {
    mediaRef.current?.stop();
    setRecording(false);
  }, []);

  const reRecord = useCallback(() => {
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    blobRef.current = null;
    metaRef.current = null;
    setElapsed(0);
    setCaptured(false);
  }, []);

  const submit = useCallback(() => {
    if (blobRef.current && metaRef.current) {
      onCompleteRef.current(blobRef.current, metaRef.current);
    }
  }, []);

  return {
    recording,
    captured,
    micError,
    elapsed,
    previewUrl,
    start,
    stop,
    reRecord,
    submit,
  };
}
