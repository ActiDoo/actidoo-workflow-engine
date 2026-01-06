// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { GenericPostResponseAction } from '@/ui5-components';
import { TaskItem, TaskItemResponse } from '@/models/models';
import { WeDataAction, WeDataKey, WeDataState } from '@/store/generic-data/setup';
import _ from 'lodash';

export const postDataResponseReducer = (state: WeDataState, action: WeDataAction): WeDataState => {
  switch (action.payload.key) {
    case WeDataKey.ADMIN_REPLACE_TASK_DATA:
    case WeDataKey.ADMIN_ASSIGN_TASK:
    case WeDataKey.ADMIN_UNASSIGN_TASK:
      return updateTaskOfWorkflow(
        state,
        (action as GenericPostResponseAction<WeDataKey, TaskItemResponse>).payload.data?.task
      );
    default:
      return state;
  }
};

const updateTaskOfWorkflow = (state: WeDataState, taskItem?: TaskItem | null): WeDataState => {
  if (taskItem) {
    const newState = _.cloneDeep(state);
    if (newState[WeDataKey.ADMIN_TASKS_OF_WORKFLOW]?.data) {
      const replaceItemIndex = newState[WeDataKey.ADMIN_TASKS_OF_WORKFLOW].data.ITEMS.findIndex(
        item => item.id === taskItem.id
      );
      if (replaceItemIndex >= 0) {
        newState[WeDataKey.ADMIN_TASKS_OF_WORKFLOW].data.ITEMS[replaceItemIndex] = taskItem;
        return newState;
      }
    }
  }
  return state;
};
