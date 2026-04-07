export interface Patient {
  patient_id: string;
  full_name: string;
  email: string;
  date_of_birth: string;
  gender: string | null;
  status: "pending" | "approved";
  pre_assigned_defect_ids: { defect_ids: string[] } | null;
  created_at: string;
}

export interface AssignedDefect {
  defect_id: string;
  name: string;
  category: string;
}

export interface PatientProfile {
  patient_id: string;
  full_name: string;
  email: string;
  date_of_birth: string;
  gender: string | null;
  status: string;
  current_streak: number;
  assigned_defects: AssignedDefect[];
}

export interface HomeData {
  has_baseline: boolean;
  full_name: string;
  today_tasks: number;
  has_approved_plan: boolean;
  plan_status: string | null;
  plan_name: string | null;
  plan_start_date: string | null;
  plan_end_date: string | null;
}

export type HomeSummary = Pick<HomeData, "has_approved_plan" | "plan_name" | "plan_start_date" | "plan_end_date">;
