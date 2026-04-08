"use client";
import { useState, useRef } from "react";
import { NeoButton } from "@/components/ui/NeoButton";
import type { RecordingMeta } from "@/types";

interface RecorderProps {
  onRecordingComplete: (blob: Blob, meta: RecordingMeta) => void;
  disabled?: boolean;
}

export function Recorder({ onRecordingComplete, disabled }: RecorderProps) {
  const [recording, setRecording] = useState(false);
  const [captured, setCaptured] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const micActivatedAtRef = useRef<string | null>(null);
  const speechStartAtRef = useRef<string | null>(null);
  const blobRef = useRef<Blob | null>(null);
  const metaRef = useRef<RecordingMeta | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

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

  async function startRecording() {
    setMicError(null);
    const stream = await navigator.mediaDevices
      .getUserMedia({ audio: true })
      .catch(() => null);
    if (!stream) {
      setMicError("Microphone access denied. Please allow microphone permission and try again.");
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
      blobRef.current = blob;
      metaRef.current = {
        micActivatedAt: micActivatedAtRef.current ?? activatedAt,
        speechStartAt: speechStartAtRef.current,
      };
      setCaptured(true);
      stream.getTracks().forEach((t) => t.stop());
    };

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
      if (!speechStartAtRef.current && rms > 0.06) {
        speechStartAtRef.current = new Date().toISOString();
      }
      animationFrameRef.current = requestAnimationFrame(monitorSpeech);
    };
    animationFrameRef.current = requestAnimationFrame(monitorSpeech);

    mr.start();
    mediaRef.current = mr;
    setRecording(true);
  }

  function stopRecording() {
    mediaRef.current?.stop();
    setRecording(false);
  }

  function handleReRecord() {
    blobRef.current = null;
    metaRef.current = null;
    setCaptured(false);
  }

  function handleSubmit() {
    if (blobRef.current && metaRef.current) {
      onRecordingComplete(blobRef.current, metaRef.current);
    }
  }

  if (disabled) {
    return (
      <div className="border-4 border-black bg-gray-100 p-4 text-center font-bold text-gray-500">
        Listen to the instruction first...
      </div>
    );
  }

  if (captured) {
    return (
      <div className="border-4 border-black p-4 space-y-3 text-center">
        <p className="text-sm font-bold text-green-700">Recording ready ✓</p>
        <div className="flex gap-3">
          <NeoButton variant="ghost" onClick={handleReRecord} className="flex-1">
            Re-record
          </NeoButton>
          <NeoButton onClick={handleSubmit} className="flex-1">
            Submit →
          </NeoButton>
        </div>
      </div>
    );
  }

  return (
    <div className="border-4 border-black p-4 space-y-3 text-center">
      {micError && (
        <p className="text-sm font-bold text-red-600">{micError}</p>
      )}
      {recording ? (
        <>
          <div className="text-[#FF6B6B] font-black animate-pulse text-lg" role="status" aria-live="polite">
            ● Recording in progress
          </div>
          <NeoButton variant="ghost" onClick={stopRecording} aria-label="Stop recording">
            Stop Recording
          </NeoButton>
        </>
      ) : (
        <NeoButton onClick={startRecording} aria-label="Start recording">
          Start Recording
        </NeoButton>
      )}
    </div>
  );
}
