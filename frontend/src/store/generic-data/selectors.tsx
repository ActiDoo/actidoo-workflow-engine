// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { AdminWorkflowInstance, UserTask } from '@/models/models';

export const useSelectCurrentTask = (id?: string): UserTask | undefined =>
  useSelector((state: State) =>
    state.data[WeDataKey.MY_USER_TASKS]?.data?.usertasks.find(t => t.id === id)
  );

export const useSelectCurrentAdminWorkflow = (id?: string): AdminWorkflowInstance | undefined =>
  useSelector((state: State) =>
    state.data[WeDataKey.ADMIN_ALL_WORKFLOWS]?.data?.ITEMS.find(t => t.id === id)
  );
export const useSelectCurrentWorkflow = (id?: string): AdminWorkflowInstance | undefined =>
  useSelector((state: State) =>
    state.data[WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS]?.data?.ITEMS.find(t => t.id === id)
  );
