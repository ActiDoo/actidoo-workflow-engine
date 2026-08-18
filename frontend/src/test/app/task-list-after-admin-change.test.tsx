// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// The open-tasks list is loaded once into the store. When the user changes something in
// the admin area that affects their own task list and comes back, the list must show the
// current state - not what was loaded before.

import { page } from 'vitest/browser';

import OpenTasks from '@/pages/tasks/open/OpenTasks';
import AdminTaskDetails from '@/pages/admin/tasks/details/AdminTaskDetails';
import { renderApp, route } from '@/test/app/support/renderApp';
import { createFakeBff, type FakeBff } from '@/test/app/support/fakeBff';
import { useFakeBackend } from '@/test/support/fakeFetchService';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

const admin = {
  id: 'user-admin',
  full_name: 'Ada Admin',
  email: 'ada@example.com',
  workflows_the_user_is_admin_for: ['OrderApproval'],
};
const bob = {
  id: 'user-bob',
  full_name: 'Bob Builder',
  email: 'bob@example.com',
  workflows_the_user_is_admin_for: [],
};

const world = () =>
  createFakeBff({
    currentUser: admin,
    users: [admin, bob],
    instances: [
      { id: 'inst-4711', name: 'OrderApproval', title: 'Order 4711' },
      { id: 'inst-4712', name: 'OrderApproval', title: 'Order 4712' },
    ],
    tasks: [
      {
        id: 'task-4711',
        title: 'Approve order',
        instanceId: 'inst-4711',
        assignedUserId: admin.id,
      },
      { id: 'task-4712', title: 'Approve order', instanceId: 'inst-4712', assignedUserId: bob.id },
    ],
  });

const routes = [
  route('/tasks/open', <OpenTasks />),
  route('/admin/all-tasks/:taskId', <AdminTaskDetails />),
];

const text = (content: string) => page.getByText(content, { exact: true });
const button = (name: string) => page.getByRole('button', { name, exact: true });

describe('Open tasks list after a change in the admin area', () => {
  let bff: FakeBff;

  beforeEach(() => {
    bff = world();
    useFakeBackend(bff.handle);
  });

  it('shows a task the admin assigned to themselves after returning to the list', async () => {
    const app = renderApp(routes, '/tasks/open');

    await expect.element(text('Order 4711')).toBeVisible();
    expect(text('Order 4712').query()).toBeNull();

    // Admin area: assign the other task to myself.
    await app.navigate('/admin/all-tasks/task-4712');
    await expect.element(text('Task Details: Approve order')).toBeVisible();
    await button('Assign user').click();
    await page.getByRole('textbox', { name: 'Search User' }).fill('Ada');
    await page.getByText('Ada Admin (ada@example.com)').click();
    await button('Assign User').click();
    await expect.poll(() => bff.callsTo('admin/assign_task')).toHaveLength(1);

    // Back to the list: it has to show the assignment.
    await app.navigate('/tasks/open');
    await expect.element(text('Order 4711')).toBeVisible();
    await expect.element(text('Order 4712')).toBeVisible();
  });
});
