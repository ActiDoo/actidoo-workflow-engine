// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

export interface LoginState {
  username?: string;
  is_logged_in?: boolean;
  can_access_wf?: boolean;
  can_access_wf_admin?: boolean;
}

export interface LoginUrl {
  login_url: string;
}

export interface UserTask {
  name: string;
  title: string;
  id: string;
  jsonschema: object;
  uischema: object;
  lane: string;
  assigned_to_me?: boolean;
  can_be_unassigned?: boolean;
  can_cancel_workflow?: boolean;
  can_delete_workflow?: boolean;
  state_completed?: boolean;
  assigned_user?: {
    id: string;
    full_name: string;
    username?: string;
    email?: string;
  };
  data?: object;
}

export interface GetUserTasksResponse {
  usertasks: UserTask[];
}

export interface SubmitTaskDataErrorResponse {
  error_schema: object;
}

export interface StartWorkflowRequest {
  name: string;
  data?: Record<string, unknown>;
}

export interface StartWorkflowResponse {
  workflow_instance_id: string;
}

export interface CopyWorkflowDataResponse {
  workflow_name: string;
  task_name: string;
  data: Record<string, unknown>;
}

export interface StartWorkflowPreviewResponse {
  name: string;
  title: string;
  subtitle?: string;
  task: UserTask;
}

export interface GetWorkflowResponse {
  workflows: Array<{
    name: string;
    title: string;
  }>;
}

export interface TaskItemResponse {
  task: TaskItem;
}

export interface WorkflowInstance {
  id: string;
  name?: string;
  title?: string;
  subtitle?: string;
  is_completed?: boolean;
  active_tasks?: ActiveTaskInstance[];
  completed_tasks?: ActiveTaskInstance[];
}
export interface AdminGraphInstance {
  id: string;
  name?: string;
  title?: string;
  created_at?: string;
}

export interface AdminWorkflowInstance {
  id: string;
  name?: string;
  title?: string;
  subtitle?: string;
  created_at?: string;
  is_completed?: boolean;
  has_task_in_error_state?: boolean;
  created_by?: User;
}

export interface MyInitiatedWorkflowInstance {
  id: string;
  name: string;
  title?: string;
  subtitle?: string;
  active_tasks?: ActiveTaskInstance[];
  created_at?: Date;
  completed_at?: Date;
}

export interface ActiveTaskInstance {
  id: string;
  name?: string;
  title?: string;
  assigned_user?: User;
}

export interface TaskItem {
  id: string;
  name?: string;
  title?: string;
  lane?: string;
  lane_roles?: string[];
  lane_initiator?: boolean;
  jsonschema?: object;
  uischema?: object;
  assigned_user?: User;
  triggered_by?: User;
  data?: object;
  state_ready?: boolean;
  state_completed?: boolean;
  state_error?: boolean;
  state_cancelled?: boolean;
  created_at?: Date;
  completed_at?: Date;
  workflow_instance?: WorkflowInstance;
  error_stacktrace?: string;
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  workflows_the_user_is_admin_for: string[];
}

export interface LocaleItem {
  /** IETF BCP-47 locale code, e.g. "en", "de-DE", "fr-CH" */
  key: string;
  /** Human-readable label, e.g. "English", "German (Germany)" */
  label: string;
}

export interface UserSettings {
  locale: string;
  supported_locales: LocaleItem[];
}

export interface PcValueLabelItem {
  value: string;
  label: string;
}

export type ComboBoxOptions = Record<string, PcValueLabelItem[]>;

export interface ReplaceTaskDataRequestData {
  task_id: string;
  data: string;
}

export interface ExecuteErroneousTaskRequestData {
  task_id: string;
}

export enum WorkflowState {
  READY = 'ready',
  COMPLETED = 'completed',
}

export interface SearchWfUsersResponse {
  options: SearchWfUserItem[];
}

export interface SearchWfUserItem {
  value: string;
  label: string;
}

export interface RefreshGetWorkflowSpec {
  id: string;
  created_at: string;
  files: RefreshGetWorkflowSpecItem[];
  name: string;
  version: number;
}

export interface RefreshGetWorkflowSpecItem {
  id: string;
  created_at: string;
  file_name: string;
  file_type: string;
  file_hash: string;
  file_content: string;
  file_bpmn_process_id: string;
}

export interface GetWorkflowStatisticsResponse {
  workflows: Array<{
    name: string;
    title: string;
    active_instances: number;
    completed_instances: number;
    estimated_saved_mins_per_instance: number;
    estimated_instances_per_year: number;
    estimated_savings_per_year: number;
  }>;
}

export interface GetSystemInformationResponse {
  build_number: string;
}

export interface TaskState {
  title: string;
  ready_counter: number;
  error_counter: number;
}

export interface GetTaskStatesPerWorkflowResponse {
  workflow_name: string;
  tasks: Record<string, TaskState>;
}

interface Bounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface BusinessObject {
  id: string;
  $type: string;
}

export interface BpmnElement {
  id: string;
  children: BpmnElement[];
  labels: string[];
  businessObject: BusinessObject;
  di: {
    id: string;
    bounds: Bounds;
  };
  x: number;
  y: number;
  width: number;
  height: number;
}
