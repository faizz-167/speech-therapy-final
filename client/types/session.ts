export interface Prompt {
  prompt_id: string;
  prompt_type: string;
  task_mode: string;
  instruction: string | null;
  display_content: string | null;
  target_response: string | null;
  scenario_context: string | null;
}

export interface AttemptScore {
  attempt_id: string;
  attempt_number: number | null;
  word_accuracy: number | null;
  phoneme_accuracy: number | null;
  fluency_score: number | null;
  speech_rate_wpm: number | null;
  speech_rate_score: number | null;
  disfluency_rate: number | null;
  pause_score: number | null;
  behavioral_score: number | null;
  emotion_score: number | null;
  dominant_emotion: string | null;
  engagement_score: number | null;
  speech_score: number | null;
  confidence_score: number | null;
  final_score: number | null;
  pass_fail: string | null;
  adaptive_decision: string | null;
  asr_transcript: string | null;
  performance_level: string | null;
  review_recommended: boolean | null;
  fail_reason: string | null;
}

export interface PollResult {
  result: string;
  score: Record<string, unknown> | null;
}

export interface RecordingMeta {
  micActivatedAt: string;
  speechStartAt: string | null;
}

export type SessionPhase = "instruction" | "record" | "uploading" | "scoring" | "scored" | "timeout";
