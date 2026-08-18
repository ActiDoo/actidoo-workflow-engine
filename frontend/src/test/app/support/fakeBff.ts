// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// In-memory stand-in for the BFF endpoints an app test touches. It keeps a small world of
// users, workflow instances and tasks, applies admin changes to it and answers the reads
// from the current state, so a test can check whether the UI reflects a change made
// elsewhere. Anything it does not know is an error - a test should never hit an
// endpoint the fake does not model.

import type { TaskItem, User, WorkflowInstance } from '@/models/models';
import type { FakeFetchCall, FakeFetchResult } from '@/test/support/fakeFetchService';

export type FakeBffCall = FakeFetchCall;

interface FakeTask {
  id: string;
  title: string;
  instanceId: string;
  assignedUserId: string | null;
}

interface FakeInstance {
  id: string;
  name: string;
  title: string;
}

export interface FakeBffOptions {
  currentUser: User;
  users: User[];
  instances: FakeInstance[];
  tasks: FakeTask[];
}

// getApiUrl() prefixes the BFF base (e.g. http://localhost/api/wfe/bff/); routes are matched
// on the part after it, without query string.
const path = (url: string): string => url.replace(/^.*\/bff\//, '').replace(/\?.*$/, '');

export const createFakeBff = (options: FakeBffOptions) => {
  const { currentUser, users, instances, tasks } = options;
  const calls: FakeBffCall[] = [];

  const userById = (id: string | null): User | undefined => users.find(user => user.id === id);
  const instanceById = (id: string): FakeInstance | undefined =>
    instances.find(instance => instance.id === id);

  const taskItem = (task: FakeTask): TaskItem => {
    const instance = instanceById(task.instanceId);
    return {
      id: task.id,
      name: task.id,
      title: task.title,
      lane: 'Approver',
      lane_roles: [],
      state_ready: true,
      created_at: new Date('2026-01-01T09:00:00Z'),
      assigned_user: userById(task.assignedUserId),
      workflow_instance: instance
        ? { id: instance.id, name: instance.name, title: instance.title }
        : undefined,
    };
  };

  // Like the backend, the open list shows an instance if one of its ready tasks is
  // available to the current user - here: assigned to them.
  const openInstancesForCurrentUser = (): WorkflowInstance[] =>
    instances
      .map(instance => ({
        id: instance.id,
        name: instance.name,
        title: instance.title,
        is_completed: false,
        active_tasks: tasks
          .filter(task => task.instanceId === instance.id && task.assignedUserId === currentUser.id)
          .map(task => ({
            id: task.id,
            name: task.id,
            title: task.title,
            assigned_user: userById(task.assignedUserId),
          })),
      }))
      .filter(instance => instance.active_tasks.length > 0);

  const handle = ({ method, url, body, queryParams }: FakeFetchCall): FakeFetchResult => {
    calls.push({ method, url: path(url), body, queryParams });
    const route = `${method} ${path(url)}`;

    switch (route) {
      case 'POST user/my_wfe_user':
        return { data: currentUser, response: 200 };

      case 'POST user/workflow_instances_with_tasks/ready':
        return { data: { ITEMS: openInstancesForCurrentUser(), NEXT_CURSOR: null }, response: 200 };

      case 'POST admin/all_tasks': {
        const wanted = queryParams?.f_id;
        const items = tasks.filter(task => !wanted || task.id === wanted).map(taskItem);
        return { data: { ITEMS: items, COUNT: items.length }, response: 200 };
      }

      case 'POST admin/search_wf_users': {
        const search = String(
          (body as { search?: string } | undefined)?.search ?? ''
        ).toLowerCase();
        const options = users
          .filter(user => `${user.full_name} ${user.email}`.toLowerCase().includes(search))
          .map(user => ({ value: user.id, label: `${user.full_name} (${user.email})` }));
        return { data: { options }, response: 200 };
      }

      case 'POST admin/assign_task': {
        const request = body as { task_id?: string; user_id?: string };
        const task = tasks.find(candidate => candidate.id === request.task_id);
        const userId = request.user_id;
        if (!task || !userId || !userById(userId)) return { data: undefined, response: 404 };
        task.assignedUserId = userId;
        return { data: taskItem(task), response: 200 };
      }

      default:
        throw new Error(`fake BFF: no handler for ${route}`);
    }
  };

  const callsTo = (urlPath: string): FakeBffCall[] => calls.filter(call => call.url === urlPath);

  return { handle, calls, callsTo };
};

export type FakeBff = ReturnType<typeof createFakeBff>;
