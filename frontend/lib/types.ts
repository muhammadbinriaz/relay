export type Workflow = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  version: number;
  is_active: boolean;
  graph: { entry: string; steps: Array<{ key: string; type: string; name?: string }> };
  created_at: string;
};

export type Step = {
  id: string;
  step_key: string;
  step_type: string;
  sequence: number;
  status: string;
  attempt: number;
  max_attempts: number;
  error: string | null;
  output: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
};

export type Run = {
  id: string;
  definition_id: string;
  status: string;
  trigger_type: string;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  error: string | null;
  current_step_key: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  steps: Step[];
};

export type Approval = {
  id: string;
  run_id: string;
  step_id: string;
  status: string;
  title: string;
  payload: Record<string, unknown>;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
};

export type AuditEvent = {
  id: string;
  event_type: string;
  message: string;
  data: Record<string, unknown>;
  run_id: string | null;
  step_id: string | null;
  created_at: string;
};
