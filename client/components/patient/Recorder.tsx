"use client";
import { useState, useRef } from "react";
import { NeoButton } from "@/components/ui/NeoButton";

interface RecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  disabled?: boolean;
}

export function Recorder({ onRecordingComplete, disabled }: RecorderProps) {
  const [recording, setRecording] = useState(false);
  const [hasRecorded, setHasRecorded] = useState(false);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream);
    chunksRef.current = [];
    mr.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    mr.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      onRecordingComplete(blob);
      setHasRecorded(true);
      stream.getTracks().forEach((t) => t.stop());
    };
    mr.start();
    mediaRef.current = mr;
    setRecording(true);
  }

  function stopRecording() {
    mediaRef.current?.stop();
    setRecording(false);
  }

  if (disabled) {
    return (
      <div className="border-4 border-black bg-gray-100 p-4 text-center font-bold text-gray-500">
        Listen to the instruction first...
      </div>
    );
  }

  return (
    <div className="border-4 border-black p-4 space-y-3 text-center">
      {recording ? (
        <>
          <div className="text-[#FF6B6B] font-black animate-pulse text-lg">● RECORDING</div>
          <NeoButton variant="ghost" onClick={stopRecording}>Stop Recording</NeoButton>
        </>
      ) : (
        <>
          {hasRecorded && <p className="text-sm font-bold text-green-700">Recording complete ✓</p>}
          <NeoButton onClick={startRecording}>
            {hasRecorded ? "Re-record" : "Start Recording"}
          </NeoButton>
        </>
      )}
    </div>
  );
}
