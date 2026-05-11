"use client";
import { NeoButton } from "@/components/ui/NeoButton";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
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

function formatTime(s: number): string {
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}

export function Recorder({ onRecordingComplete, disabled }: RecorderProps) {
  const {
    recording,
    captured,
    micError,
    elapsed,
    previewUrl,
    start,
    stop,
    reRecord,
    submit,
  } = useAudioRecorder(onRecordingComplete);

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
        {previewUrl && (
          <audio controls className="w-full border-4 border-neo-black" src={previewUrl}>
            Your browser does not support audio playback.
          </audio>
        )}
        <div className="grid grid-cols-2 gap-3">
          <NeoButton variant="ghost" onClick={reRecord} className="w-full">Re-record</NeoButton>
          <NeoButton onClick={submit} className="w-full">Submit →</NeoButton>
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

          <NeoButton variant="ghost" onClick={stop} className="w-full" aria-label="Stop recording">
            ■ Stop Recording
          </NeoButton>
        </div>
      ) : (
        <NeoButton onClick={start} className="w-full" aria-label="Start recording" size="lg">
          🎤 Start Recording
        </NeoButton>
      )}
    </div>
  );
}
