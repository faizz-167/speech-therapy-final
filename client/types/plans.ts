export interface Assignment {
  assignment_id: string;
  task_id: string;
  task_name: string;
  task_mode: string;
  day_index: number | null;
  status: string;
  priority_order: number | null;
  current_level?: string | null;
}

export interface Plan {
  plan_id: string;
  plan_name: string;
  start_date: string | null;
  end_date: string | null;
  status: "draft" | "approved";
  goals: string | null;
  assignments: Assignment[];
}

export interface PlanRevisionEntry {
  id: string;
  action: string;
  actor_role: string;
  change_summary: string | null;
  created_at: string;
}
