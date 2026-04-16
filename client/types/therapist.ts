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

export interface TherapistProfile {
  therapist_id: string;
  full_name: string;
  email: string;
  therapist_code: string;
  license_number: string | null;
  specialization: string | null;
  years_of_experience: number | null;
}

export interface TherapistDashboard {
  total_patients: number;
  approved_patients: number;
  pending_patients: number;
  patients_without_baseline: number;
  patients_without_approved_plan: number;
  plans_pending_approval: number;
  unread_notification_count: number;
}

export interface ApproveRequest {
  defect_ids: string[];
  primary_diagnosis?: string;
  clinical_notes?: string;
}

export interface Notification {
  id: string;
  notification_type: 'patient_registered' | 'review_flagged' | string;
  message: string;
  is_read: boolean;
  created_at: string;
  patient_id: string | null;
  attempt_id: string | null;
}

export interface AdaptationStep {
  from_level: string;
  to_level: string;
  attempts_used: number;
  reason: string;
  final_score: number;
}

export interface AdaptationEvent {
  session_id: string;
  session_date: string;
  task_id: string;
  task_name: string;
  adaptation_count: number;
  escalated: boolean;
  adaptation_history: AdaptationStep[];
  adaptation_report: Record<string, unknown> | null;
  linked_plan: RegeneratedPlan | null;
}

export interface RegeneratedAssignment {
  assignment_id: string;
  task_id: string;
  task_name: string;
  initial_level_name: string | null;
  day_index: number | null;
}

export interface RegeneratedPlan {
  plan_id: string;
  plan_name: string;
  status: "draft" | "approved" | "archived";
  created_at: string;
  regeneration_note: string | null;
  assignments: RegeneratedAssignment[];
}

export interface AdaptationActivity {
  adaptation_events: AdaptationEvent[];
  regenerated_plans: RegeneratedPlan[];
}
