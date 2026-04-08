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
}

export interface ApproveRequest {
  defect_ids: string[];
  primary_diagnosis?: string;
  clinical_notes?: string;
}
