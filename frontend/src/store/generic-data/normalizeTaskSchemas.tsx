// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import _ from 'lodash';
import { GetUserTasksResponse, StartWorkflowPreviewResponse, UserTask } from '@/models/models';
import { WeDataKey } from '@/store/generic-data/setup';

/**
 * - jsonschema: rjsf 5 initialized every array field with an empty list; rjsf 6 leaves
 *   optional arrays undefined — but workflow code relies on the array keys being present
 *   in the submitted task data. Inject "default": [] so rjsf 6 fills the empty lists like
 *   rjsf 5 did. Being type-based, this also covers old schema snapshots of running
 *   instances migrated from the legacy fork.
 * - uischema: "ui:copyable" enables rjsf's copy-row button (ArrayField uiOptions.copyable)
 *   on itemgroups, which the legacy uischema never carried.
 */

type JsonObject = Record<string, any>;

const isObject = (value: unknown): value is JsonObject =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const hasArrayType = (schema: JsonObject): boolean => {
  const type = schema.type;
  return type === 'array' || (Array.isArray(type) && type.includes('array'));
};

// The form transformation nests fields only via "properties" and "items"
// (itemgroups: array → items(object) → properties), so those are the only
// subschema carriers that need to be walked.
const normalizeArrayDefaultsInJsonSchema = (schema: unknown): void => {
  if (!isObject(schema)) return;

  if (hasArrayType(schema) && !Object.prototype.hasOwnProperty.call(schema, 'default')) {
    schema.default = [];
  }

  Object.values(schema.properties ?? {}).forEach(normalizeArrayDefaultsInJsonSchema);
  normalizeArrayDefaultsInJsonSchema(schema.items);
};

// Itemgroups are recognizable by "ui:arrayAddButtonText", which only the backend's
// itemgroup transformation emits.
const normalizeItemgroupCopyableInUiSchema = (uischema: unknown): void => {
  if (!isObject(uischema)) return;

  if (
    Object.prototype.hasOwnProperty.call(uischema, 'ui:arrayAddButtonText') &&
    !Object.prototype.hasOwnProperty.call(uischema, 'ui:copyable')
  ) {
    uischema['ui:copyable'] = true;
  }

  Object.values(uischema).forEach(normalizeItemgroupCopyableInUiSchema);
};

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
