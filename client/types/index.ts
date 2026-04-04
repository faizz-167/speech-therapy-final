export interface User {
  user_id: string;
  email: string;
  full_name: string;
  role: "therapist" | "patient";
}

export interface Patient {
  patient_id: string;
  full_name: string;
  email: string;
  date_of_birth: string;
  gender: string | null;
  status: "pending" | "approved";
  pre_assigned_defect_ids: { defect_ids: string[] } | null;
  primary_diagnosis: string | null;
  created_at: string;
}

export interface Defect {
  defect_id: string;
  code: string;
  name: string;
  category: string;
}

export interface Task {
  task_id: string;
  name: string;
  type: string;
  task_mode: string;
  description: string | null;
}

export interface Assignment {
  assignment_id: string;
  task_id: string;
  task_name: string;
  task_mode: string;
  day_index: number;
  status: string;
  priority_order: number | null;
}

export interface Plan {
  plan_id: string;
  plan_name: string;
  start_date: string;
  end_date: string;
  status: "draft" | "approved";
  goals: string | null;
  assignments: Assignment[];
}

export interface Prompt {
  prompt_id: string;
  prompt_type: "warmup" | "exercise";
  task_mode: string;
  instruction: string | null;
  display_content: string | null;
  target_response: string | null;
  scenario_context: string | null;
}

export interface AttemptScore {
  attempt_id: string;
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
  final_score: number | null;
  pass_fail: string | null;
  adaptive_decision: string | null;
  asr_transcript: string | null;
  performance_level: string | null;
}
