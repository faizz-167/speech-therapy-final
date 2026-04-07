export interface BaselineItem {
  item_id: string;
  task_name: string | null;
  instruction: string | null;
  display_content: string | null;
  expected_output: string | null;
  response_type: string | null;
  target_phoneme: string | null;
  formula_weights: Record<string, number> | null;
  fusion_weights: Record<string, number> | null;
  wpm_range: Record<string, number> | null;
}

export interface BaselineSection {
  section_id: string;
  section_name: string;
  instructions: string | null;
  order_index: number;
  items: BaselineItem[];
}

export interface BaselineAssessment {
  baseline_id: string;
  name: string;
  domain: string;
  sections: BaselineSection[];
}

export interface AttemptResult {
  attempt_id: string;
  result: string;
  computed_score: number | null;
  phoneme_accuracy: number | null;
  asr_transcript: string | null;
}

export interface BaselineResult {
  result_id: string;
  baseline_name: string;
  raw_score: number;
  level: string;
  assessed_on: string;
}
