export interface WeeklyPoint {
  week: string;
  avg_score: number;
  attempts: number;
}

export interface TaskMetric {
  task_id: string;
  task_name: string;
  overall_accuracy: number;
  avg_phoneme_accuracy: number | null;
  phoneme_accuracy_count: number;
  total_attempts: number;
  current_level: string | null;
  pass_rate: number;
  last_attempt_result: string | null;
}

export interface Progress {
  total_attempts: number;
  avg_final_score: number;
  avg_phoneme_accuracy: number | null;
  phoneme_accuracy_count: number;
  pass_rate: number;
  weekly_trend: WeeklyPoint[];
  task_metrics: TaskMetric[];
  dominant_emotion: string | null;
}
