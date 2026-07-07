// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import _ from 'lodash';
import { GetUserTasksResponse, StartWorkflowPreviewResponse, UserTask } from '@/models/models';
import { WeDataKey } from '@/store/generic-data/setup';
import {
  isObject,
  normalizeArrayDefaultsInJsonSchema,
  normalizeItemgroupCopyableInUiSchema,
} from '@/store/generic-data/schemaNormalization';

/**
 * - jsonschema: rjsf 5 initialized every array field with an empty list; rjsf 6 leaves
 *   optional arrays undefined — but workflow code relies on the array keys being present
 *   in the submitted task data. Inject "default": [] so rjsf 6 fills the empty lists like
 *   rjsf 5 did.
 * - uischema: "ui:copyable" enables rjsf's copy-row button
 */

const normalizeTask = (task: UserTask): UserTask => {
  if (!isObject(task) || !isObject(task.jsonschema)) return task;

  // Only the schemas are normalized; the rest of the task is shared unchanged.
  const jsonschema = _.cloneDeep(task.jsonschema);
  normalizeArrayDefaultsInJsonSchema(jsonschema);

  if (!isObject(task.uischema)) return { ...task, jsonschema };

  const uischema = _.cloneDeep(task.uischema);
  normalizeItemgroupCopyableInUiSchema(uischema);
  return { ...task, jsonschema, uischema };
};

const normalizeUserTasksResponse = (data: GetUserTasksResponse): GetUserTasksResponse => ({
  ...data,
  usertasks: data.usertasks.map(normalizeTask),
});

const normalizeStartWorkflowPreviewResponse = (
  data: StartWorkflowPreviewResponse
): StartWorkflowPreviewResponse => ({
  ...data,
  task: normalizeTask(data.task),
});

export const normalizeTaskSchemasForResponse = (key: WeDataKey, data: any): any => {
  if (!data) return data;

  switch (key) {
    case WeDataKey.MY_USER_TASKS:
      if (!Array.isArray(data.usertasks)) return data;
      return normalizeUserTasksResponse(data as GetUserTasksResponse);
    case WeDataKey.START_WORKFLOW_PREVIEW:
      if (!isObject(data.task)) return data;
      return normalizeStartWorkflowPreviewResponse(data as StartWorkflowPreviewResponse);
    default:
      return data;
  }
};
