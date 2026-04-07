export interface WeeklyPoint {
  week: string;
  avg_score: number;
  attempts: number;
}

export interface TaskMetric {
  task_name: string;
  overall_accuracy: number;
  total_attempts: number;
  current_level: string | null;
}

export interface Progress {
  total_attempts: number;
  avg_final_score: number;
  pass_rate: number;
  weekly_trend: WeeklyPoint[];
  task_metrics: TaskMetric[];
  dominant_emotion: string | null;
}
