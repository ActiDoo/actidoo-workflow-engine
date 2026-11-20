// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { StartWorkflowPreviewResponse, StartWorkflowRequest } from '@/models/models';
import { getApiUrl } from '@/services/ApiService';
import { normalizeStartWorkflowPreviewResponse } from '@/store/generic-data/normalizeTaskSchemas';
import { startWorkflowPreviewPath, WeDataKey } from '@/store/generic-data/setup';
import { fetchPost } from '@/ui5-components';

export const workflowPreviewKey = (request: StartWorkflowRequest | null, visit: string) =>
  [WeDataKey.START_WORKFLOW_PREVIEW, request, visit] as const;

export async function loadWorkflowPreview(
  request: StartWorkflowRequest
): Promise<StartWorkflowPreviewResponse> {
  const { response, data } = await fetchPost(getApiUrl(startWorkflowPreviewPath), request);
  if (response !== 200) throw new Error('Could not load workflow preview');
  return normalizeStartWorkflowPreviewResponse(data);
}
