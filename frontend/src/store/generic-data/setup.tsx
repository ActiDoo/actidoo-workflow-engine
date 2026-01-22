// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

/**
 * Holds abstractions to keep the boilerplate code low for data fetching:
 * Normally you have to handle each new request/response and its payload separately and you would have to write separate actions, sagas, reducers and selectors.
 * Therefore the handling is abstracted here and you just have to add new definitions for new routes. */

import {
  FetchMethods,
  GenericDataAction,
  GenericDataEntry,
  ItemsAndCountResponse,
  StringDict,
} from '@/ui5-components';
import {
  AdminGraphInstance,
  AdminUser,
  AdminWorkflowInstance,
  ExecuteErroneousTaskRequestData,
  GetSystemInformationResponse,
  GetUserDetailResponse,
  GetUserTasksResponse,
  GetWorkflowResponse,
  GetWorkflowStatisticsResponse,
  MyInitiatedWorkflowInstance,
  RefreshGetWorkflowSpec,
  ReplaceTaskDataRequestData,
  SearchWfUsersResponse,
  StartWorkflowResponse,
  CopyWorkflowDataResponse,
  StartWorkflowPreviewResponse,
  SubmitTaskDataErrorResponse,
  TaskItem,
  TaskItemResponse,
  User,
  UserSettings,
  WorkflowInstance,
  GetTaskStatesPerWorkflowResponse
} from '@/models/models';

// KEY DEFINITION
export enum WeDataKey {
  MY_USER_TASKS = 'my-user-tasks',
  SUBMIT_TASK_DATA = 'submit-task-data',
  START_WORKFLOW = 'start-workflow',
  WORKFLOWS = 'workflows',
  WORKFLOW_INSTANCES_WITH_TASKS = 'workflow-instances-with-tasks',
  MY_OPEN_WORKFLOW_INSTANCES = 'my-open-workflow-instances',
  MY_COMPLETED_WORKFLOW_INSTANCES = 'my-completed-workflow-instances',
  ASSIGN_TASK_TO_ME = 'assign-task-to-me',
  UNASSIGN_TASK_FROM_ME = 'unassign-task-from-me',
  CANCEL_WORKFLOW = 'cancel-workflow',
  DELETE_WORKFLOW = 'delete-workflow',
  COPY_INSTANCE = 'copy-instance',
  START_WORKFLOW_PREVIEW = 'start-workflow-preview',
  WFE_USER = 'wfe-user',
  USER_SETTINGS = 'user-settings',
  REFRESH_GET_WORKFLOW_SPEC = 'refresh_get_workflow_spec',
  WORKFLOW_STATISTICS = 'workflow_statistics',
  ADMIN_ALL_TASKS = 'admin_all_tasks',
  ADMIN_ALL_WORKFLOWS = 'admin_all_workflows',
  ADMIN_ALL_USERS = 'admin_all_users',
  ADMIN_GRAPH_OBJECTS = 'admin_all_graph_objects',
  ADMIN_TASKS_OF_WORKFLOW = 'admin_tasks_of_workflow',
  ADMIN_REPLACE_TASK_DATA = 'admin_replace_task_data',
  ADMIN_EXECUTE_ERRONEOUS_TASK = 'admin_execute_erroneous_task',
  ADMIN_ASSIGN_TASK = 'admin_assign_task',
  ADMIN_UNASSIGN_TASK = 'admin_unassign_task',
  ADMIN_USER_DETAIL = 'admin_user_detail',
  ADMIN_SET_USER_DELEGATIONS = 'admin_set_user_delegations',
  ADMIN_SEARCH_WF_USERS = 'admin_search_wf_users',
  ADMIN_CANCEL_WORKFLOW_INSTANCE = 'admin_cancel_workflow_instance',
  ADMIN_GET_SYSTEM_INFORMATION = 'admin_get_system_information',
  ADMIN_GET_TASK_STATES_PER_WORKFLOW = 'admin_get_task_states_per_workflow',
}

interface WorkflowInstanceTable extends ItemsAndCountResponse<WorkflowInstance> {}

interface MyInitiatedWorkflowInstanceTable
  extends ItemsAndCountResponse<MyInitiatedWorkflowInstance> {}

interface AllTasksTable extends ItemsAndCountResponse<TaskItem> {}

interface AllWorkflowsTable extends ItemsAndCountResponse<AdminWorkflowInstance> {}

interface AllUsersTable extends ItemsAndCountResponse<AdminUser> {}

interface AllGraphObjects extends ItemsAndCountResponse<AdminGraphInstance> {}

// STATE DEFINITION
export interface WeDataState {
  [WeDataKey.MY_USER_TASKS]: GenericDataEntry<GetUserTasksResponse> | null;
  [WeDataKey.SUBMIT_TASK_DATA]:
    | GenericDataEntry<GetUserTasksResponse>
    | GenericDataEntry<SubmitTaskDataErrorResponse>
    | null;
  [WeDataKey.START_WORKFLOW]: GenericDataEntry<StartWorkflowResponse> | null;
  [WeDataKey.WORKFLOWS]: GenericDataEntry<GetWorkflowResponse> | null;
  [WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS]: GenericDataEntry<WorkflowInstanceTable> | null;
  [WeDataKey.MY_OPEN_WORKFLOW_INSTANCES]: GenericDataEntry<MyInitiatedWorkflowInstanceTable> | null;
  [WeDataKey.MY_COMPLETED_WORKFLOW_INSTANCES]: GenericDataEntry<MyInitiatedWorkflowInstanceTable> | null;
  [WeDataKey.ASSIGN_TASK_TO_ME]: GenericDataEntry<string> | null;
  [WeDataKey.UNASSIGN_TASK_FROM_ME]: GenericDataEntry<string> | null;
  [WeDataKey.CANCEL_WORKFLOW]: GenericDataEntry<string> | null;
  [WeDataKey.DELETE_WORKFLOW]: GenericDataEntry<string> | null;
  [WeDataKey.COPY_INSTANCE]: GenericDataEntry<CopyWorkflowDataResponse> | null;
  [WeDataKey.START_WORKFLOW_PREVIEW]: GenericDataEntry<StartWorkflowPreviewResponse> | null;
  [WeDataKey.WFE_USER]: GenericDataEntry<User> | null;
  [WeDataKey.USER_SETTINGS]: GenericDataEntry<UserSettings> | null;
  [WeDataKey.REFRESH_GET_WORKFLOW_SPEC]: GenericDataEntry<RefreshGetWorkflowSpec> | null;
  [WeDataKey.WORKFLOW_STATISTICS]: GenericDataEntry<GetWorkflowStatisticsResponse> | null;
  [WeDataKey.ADMIN_ALL_TASKS]: GenericDataEntry<AllTasksTable> | null;
  [WeDataKey.ADMIN_ALL_WORKFLOWS]: GenericDataEntry<AllWorkflowsTable> | null;
  [WeDataKey.ADMIN_ALL_USERS]: GenericDataEntry<AllUsersTable> | null;
  [WeDataKey.ADMIN_GRAPH_OBJECTS]: GenericDataEntry<AllGraphObjects> | null;
  [WeDataKey.ADMIN_TASKS_OF_WORKFLOW]: GenericDataEntry<AllTasksTable> | null;
  [WeDataKey.ADMIN_REPLACE_TASK_DATA]: GenericDataEntry<ReplaceTaskDataRequestData> | null;
  [WeDataKey.ADMIN_EXECUTE_ERRONEOUS_TASK]: GenericDataEntry<ExecuteErroneousTaskRequestData> | null;
  [WeDataKey.ADMIN_ASSIGN_TASK]: GenericDataEntry<TaskItem> | null;
  [WeDataKey.ADMIN_UNASSIGN_TASK]: GenericDataEntry<TaskItem> | null;
  [WeDataKey.ADMIN_USER_DETAIL]: GenericDataEntry<GetUserDetailResponse> | null;
  [WeDataKey.ADMIN_SET_USER_DELEGATIONS]: GenericDataEntry<GetUserDetailResponse> | null;
  [WeDataKey.ADMIN_SEARCH_WF_USERS]: GenericDataEntry<SearchWfUsersResponse> | null;
  [WeDataKey.ADMIN_CANCEL_WORKFLOW_INSTANCE]: GenericDataEntry<object> | null;
  [WeDataKey.ADMIN_GET_SYSTEM_INFORMATION]: GenericDataEntry<GetSystemInformationResponse> | null;
  [WeDataKey.ADMIN_GET_TASK_STATES_PER_WORKFLOW]: GenericDataEntry<GetTaskStatesPerWorkflowResponse> | null;
}

// API DEFINITION
export const WeApiUrl = (
  key: string,
  params?: StringDict,
  fetchMethod?: FetchMethods
): string | undefined => {
  switch (key) {
    case WeDataKey.MY_USER_TASKS:
      return `user/my_usertasks/${params?.state}`;
    case WeDataKey.SUBMIT_TASK_DATA:
      return 'user/submit_task_data';
    case WeDataKey.START_WORKFLOW:
      return 'user/start_workflow';
    case WeDataKey.WORKFLOWS:
      return 'user/workflows';
    case WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS:
      return `user/workflow_instances_with_tasks/${params?.state}`;
    case WeDataKey.MY_COMPLETED_WORKFLOW_INSTANCES:
    case WeDataKey.MY_OPEN_WORKFLOW_INSTANCES:
      return 'user/my_initiated_workflow_instances';
    case WeDataKey.ASSIGN_TASK_TO_ME:
      return 'user/assign_task_to_me';
    case WeDataKey.UNASSIGN_TASK_FROM_ME:
      return 'user/unassign_task_from_me';
    case WeDataKey.CANCEL_WORKFLOW:
      return 'user/cancel_workflow';
    case WeDataKey.DELETE_WORKFLOW:
      return 'user/delete_workflow';
    case WeDataKey.COPY_INSTANCE:
      return `user/workflow_instances/${params?.workflow_instance_id}/copy_data`;
    case WeDataKey.START_WORKFLOW_PREVIEW:
      return 'user/start_workflow_preview_with_data';
    case WeDataKey.WFE_USER:
      return 'user/my_wfe_user';
    case WeDataKey.USER_SETTINGS:
      return 'user/user_settings';
    case WeDataKey.REFRESH_GET_WORKFLOW_SPEC:
      return 'user/refresh_get_workflow_spec';
    case WeDataKey.WORKFLOW_STATISTICS:
      return 'user/statistics';
    case WeDataKey.ADMIN_ALL_TASKS:
    case WeDataKey.ADMIN_TASKS_OF_WORKFLOW:
      return 'admin/all_tasks';
    case WeDataKey.ADMIN_ALL_WORKFLOWS:
      return 'admin/all_workflow_instances';
    case WeDataKey.ADMIN_ALL_USERS:
      return 'admin/all_users';
    case WeDataKey.ADMIN_GRAPH_OBJECTS:
      return 'admin/statistics_information'
    case WeDataKey.ADMIN_REPLACE_TASK_DATA:
      return 'admin/replace_task_data';
    case WeDataKey.ADMIN_EXECUTE_ERRONEOUS_TASK:
      return 'admin/execute_erroneous_task';
    case WeDataKey.ADMIN_ASSIGN_TASK:
      return 'admin/assign_task';
    case WeDataKey.ADMIN_UNASSIGN_TASK:
      return 'admin/unassign_task';
    case WeDataKey.ADMIN_USER_DETAIL:
      return 'admin/user_detail';
    case WeDataKey.ADMIN_SET_USER_DELEGATIONS:
      return 'admin/set_user_delegations';
    case WeDataKey.ADMIN_SEARCH_WF_USERS:
      return 'admin/search_wf_users';
    case WeDataKey.ADMIN_CANCEL_WORKFLOW_INSTANCE:
      return 'admin/cancel_workflow_instance';
    case WeDataKey.ADMIN_GET_SYSTEM_INFORMATION:
      return 'admin/system_information';
    case WeDataKey.ADMIN_GET_TASK_STATES_PER_WORKFLOW:
      return `admin/get_task_states_per_workflow?wf_name=${params?.wf_name}`;
    default:
      return undefined;
  }
};

export const initState: WeDataState = {
  [WeDataKey.MY_USER_TASKS]: null,
  [WeDataKey.START_WORKFLOW]: null,
  [WeDataKey.SUBMIT_TASK_DATA]: null,
  [WeDataKey.WORKFLOWS]: null,
  [WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS]: null,
  [WeDataKey.MY_OPEN_WORKFLOW_INSTANCES]: null,
  [WeDataKey.MY_COMPLETED_WORKFLOW_INSTANCES]: null,
  [WeDataKey.ASSIGN_TASK_TO_ME]: null,
  [WeDataKey.UNASSIGN_TASK_FROM_ME]: null,
  [WeDataKey.CANCEL_WORKFLOW]: null,
  [WeDataKey.DELETE_WORKFLOW]: null,
  [WeDataKey.COPY_INSTANCE]: null,
  [WeDataKey.START_WORKFLOW_PREVIEW]: null,
  [WeDataKey.WFE_USER]: null,
  [WeDataKey.USER_SETTINGS]: null,
  [WeDataKey.REFRESH_GET_WORKFLOW_SPEC]: null,
  [WeDataKey.WORKFLOW_STATISTICS]: null,
  [WeDataKey.ADMIN_ALL_TASKS]: null,
  [WeDataKey.ADMIN_ALL_WORKFLOWS]: null,
  [WeDataKey.ADMIN_ALL_USERS]: null,
  [WeDataKey.ADMIN_TASKS_OF_WORKFLOW]: null,
  [WeDataKey.ADMIN_GRAPH_OBJECTS]: null,
  [WeDataKey.ADMIN_REPLACE_TASK_DATA]: null,
  [WeDataKey.ADMIN_EXECUTE_ERRONEOUS_TASK]: null,
  [WeDataKey.ADMIN_ASSIGN_TASK]: null,
  [WeDataKey.ADMIN_UNASSIGN_TASK]: null,
  [WeDataKey.ADMIN_USER_DETAIL]: null,
  [WeDataKey.ADMIN_SET_USER_DELEGATIONS]: null,
  [WeDataKey.ADMIN_SEARCH_WF_USERS]: null,
  [WeDataKey.ADMIN_CANCEL_WORKFLOW_INSTANCE]: null,
  [WeDataKey.ADMIN_GET_SYSTEM_INFORMATION]: null,
  [WeDataKey.ADMIN_GET_TASK_STATES_PER_WORKFLOW]: null,
};

// ACTION DEFINITION
export type WeDataGetResponseTypes =
  | GetUserTasksResponse
  | SubmitTaskDataErrorResponse
  | StartWorkflowResponse
  | CopyWorkflowDataResponse
  | StartWorkflowPreviewResponse
  | GetWorkflowResponse
  | GetWorkflowStatisticsResponse
  | GetSystemInformationResponse
  | TaskItemResponse
  | GetUserDetailResponse
  | ItemsAndCountResponse<AdminUser>
  | string;

export type WeDataAction = GenericDataAction<WeDataKey, WeDataGetResponseTypes>;
