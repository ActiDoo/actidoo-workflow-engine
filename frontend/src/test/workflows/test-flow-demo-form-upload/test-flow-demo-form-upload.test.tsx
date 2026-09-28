// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

// Workflow: backend/actidoo_wfe/wf/testdata/processes/TestFlowDemoFormUpload — see ../README.md.

import { page } from 'vitest/browser';
import { renderTaskForm } from '@/test/workflows/support/renderTaskForm';
import uploadFiles from './upload-files.fixture.json';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

describe('Test Flow Demo Form Upload — file picker', () => {
  it('shows the allowed file types and rejects other files', async () => {
    const { field, uploadFile } = renderTaskForm(uploadFiles);

    await expect.element(page.getByText('Allowed: .csv, .pdf')).toBeVisible();
    await field('file_accept')
      .getByCss('input[type="file"]')
      .upload(new File(['Hallo'], 'note.txt', { type: 'text/plain' }));
    await uploadFile('file_accept', new File(['%PDF'], 'report.pdf', { type: 'application/pdf' }));

    await expect.element(page.getByText('note.txt', { exact: true })).not.toBeInTheDocument();
  });
});
