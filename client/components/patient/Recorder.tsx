"use client";
import { useEffect, useState, useRef } from "react";
import { NeoButton } from "@/components/ui/NeoButton";
import type { RecordingMeta } from "@/types";

interface RecorderProps {
  onRecordingComplete: (blob: Blob, meta: RecordingMeta) => void;
  disabled?: boolean;
}

function WaveformVisualizer({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <div className="flex items-center justify-center gap-1 h-10 my-2" aria-hidden="true">
      {Array.from({ length: 7 }, (_, i) => (
        <div
          key={i}
          className={`w-2.5 bg-neo-accent border-2 border-neo-black rounded-none animate-wave-${i + 1}`}
          style={{ height: "36px", transformOrigin: "center" }}
        />
      ))}
    </div>
  );
}

export function Recorder({ onRecordingComplete, disabled }: RecorderProps) {
  const [recording, setRecording] = useState(false);
  const [captured, setCaptured] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const micActivatedAtRef = useRef<string | null>(null);
  const speechStartAtRef = useRef<string | null>(null);
  const blobRef = useRef<Blob | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const metaRef = useRef<RecordingMeta | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      stopLevelTracking();
      if (timerRef.current) clearInterval(timerRef.current);
      if (previewUrlRef.current) { URL.revokeObjectURL(previewUrlRef.current); previewUrlRef.current = null; }
    };
  }, []);

  function stopLevelTracking() {
    if (animationFrameRef.current !== null) { cancelAnimationFrame(animationFrameRef.current); animationFrameRef.current = null; }
    analyserRef.current?.disconnect();
    analyserRef.current = null;
    if (audioContextRef.current) { void audioContextRef.current.close(); audioContextRef.current = null; }
  }

  async function startRecording() {
    setMicError(null);
    setElapsed(0);
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true }).catch(() => null);
    if (!stream) { setMicError("Microphone access denied. Please allow microphone permission and try again."); return; }

    const mr = new MediaRecorder(stream);
    const activatedAt = new Date().toISOString();
    micActivatedAtRef.current = activatedAt;
    speechStartAtRef.current = null;
    chunksRef.current = [];
    blobRef.current = null;
    metaRef.current = null;

    mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    mr.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      stopLevelTracking();
      if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
      blobRef.current = blob;
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = URL.createObjectURL(blob);
      metaRef.current = { micActivatedAt: micActivatedAtRef.current ?? activatedAt, speechStartAt: speechStartAtRef.current };
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
      for (const value of data) { const centered = (value - 128) / 128; sumSquares += centered * centered; }
      const rms = Math.sqrt(sumSquares / data.length);
      if (!speechStartAtRef.current && rms > 0.06) speechStartAtRef.current = new Date().toISOString();
      animationFrameRef.current = requestAnimationFrame(monitorSpeech);
    };
    animationFrameRef.current = requestAnimationFrame(monitorSpeech);

    mr.start();
    mediaRef.current = mr;
    setRecording(true);

    // Timer
    timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
  }

  function stopRecording() {
    mediaRef.current?.stop();
    setRecording(false);
  }

  function handleReRecord() {
    if (previewUrlRef.current) { URL.revokeObjectURL(previewUrlRef.current); previewUrlRef.current = null; }
    blobRef.current = null; metaRef.current = null;
    setElapsed(0);
    setCaptured(false);
  }

  function handleSubmit() {
    if (blobRef.current && metaRef.current) onRecordingComplete(blobRef.current, metaRef.current);
  }

  function formatTime(s: number): string {
    return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
  }

  if (disabled) {
    return (
      <div className="border-4 border-neo-black/30 bg-neo-bg p-5 text-center font-bold text-neo-black/50">
        Listen to the instruction first…
      </div>
    );
  }

  if (captured) {
    return (
      <div className="space-y-4 animate-fade-up">
        <div className="border-4 border-neo-black bg-neo-secondary px-4 py-2 flex items-center gap-2">
          <span className="font-black text-sm">✓</span>
          <span className="font-black uppercase text-xs tracking-widest">Recording Ready ({formatTime(elapsed)})</span>
        </div>
        {previewUrlRef.current && (
          <audio controls className="w-full border-4 border-neo-black" src={previewUrlRef.current}>
            Your browser does not support audio playback.
          </audio>
        )}
        <div className="grid grid-cols-2 gap-3">
          <NeoButton variant="ghost" onClick={handleReRecord} className="w-full">Re-record</NeoButton>
          <NeoButton onClick={handleSubmit} className="w-full">Submit →</NeoButton>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {micError && (
        <div className="border-4 border-neo-black bg-neo-accent px-4 py-2 text-sm font-bold">⚠ {micError}</div>
      )}

      {recording ? (
        <div className="space-y-3 animate-fade-up">
          {/* Timer */}
          <div className="border-4 border-neo-black bg-neo-accent flex items-center justify-between px-4 py-2">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 bg-neo-black rounded-full animate-pulse inline-block" aria-hidden="true"></span>
              <span className="font-black uppercase text-xs tracking-widest" role="status" aria-live="polite">Recording</span>
            </div>
            <span className="font-black text-lg tabular-nums">{formatTime(elapsed)}</span>
          </div>

          {/* Waveform */}
          <WaveformVisualizer active={recording} />

          <NeoButton variant="ghost" onClick={stopRecording} className="w-full" aria-label="Stop recording">
            ■ Stop Recording
          </NeoButton>
        </div>
      ) : (
        <NeoButton onClick={startRecording} className="w-full" aria-label="Start recording" size="lg">
          🎤 Start Recording
        </NeoButton>
      )}
    </div>
  );
}
