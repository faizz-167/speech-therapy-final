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
