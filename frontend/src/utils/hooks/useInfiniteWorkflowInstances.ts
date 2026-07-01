// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useCallback, useEffect, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { isEqual, omit } from 'lodash';
import { CursorItemsResponse, GenericRequestSignature, StringDict } from '@/ui5-components';
import { State } from '@/store';
import { WeDataAction, WeDataKey } from '@/store/generic-data/setup';
import { postRequest } from '@/store/generic-data/actions';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { WorkflowInstance, WorkflowState } from '@/models/models';

export const PAGE_SIZE = 100;

const buildQueryParams = (search: string, cursor?: string | null): StringDict => {
  const queryParams: StringDict = { limit: String(PAGE_SIZE) };
  if (search) queryParams.search = search;
  if (cursor) queryParams.cursor = cursor;
  return queryParams;
};

/**
 * The canonical sidebar refresh (page 1, no search): task submit, backToList and
 * workflow start dispatch this so the list reflects the change without a
 * remount. It produces exactly the signature the sidebar derives for an empty
 * search — anything else would trigger a redundant correcting request.
 */
export const refreshWorkflowInstancesWithTasks = (state: WorkflowState): WeDataAction =>
  postRequest(WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS, {}, { state }, buildQueryParams(''));

/** Does the signature describe this query (any page of it — the cursor is ignored)? */
const matchesQuery = (
  signature: GenericRequestSignature | undefined,
  params: StringDict,
  queryParams: StringDict
): boolean =>
  isEqual(signature?.params, params) &&
  isEqual(omit(signature?.queryParams ?? {}, ['cursor']), queryParams);

export interface UseInfiniteWorkflowInstancesResult {
  items: WorkflowInstance[];
  loadingInitial: boolean;
  loadingMore: boolean;
  error: boolean;
  hasMore: boolean;
  loadMore: () => void;
  reload: () => void;
}

/**
 * Keyset-paginated loader for the "Aufgaben" sidebar (infinite scroll + backend
 * search), backed by the generic-data store: pages accumulate via the store's
 * append merge, and any plain `postRequest`/`refreshWorkflowInstancesWithTasks`
 * on the key refreshes the list from page 1 — no private fetch state.
 */
export const useInfiniteWorkflowInstances = (
  dataKey: WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS,
  wfState: WorkflowState,
  search: string
): UseInfiniteWorkflowInstancesResult => {
  const dispatch = useDispatch();
  const entry = useSelector((state: State) => state.data[dataKey]);
  const loadingReplace = useSelectUiLoading(dataKey, 'POST');
  const loadingAppend = useSelectUiLoading(dataKey, 'APPEND');

  const params = useMemo<StringDict>(() => ({ state: wfState }), [wfState]);
  const queryParams = useMemo<StringDict>(() => buildQueryParams(search), [search]);

  // Declarative load: whenever the key's latest request (cursor ignored) differs
  // from the desired query — mount, state/search switch, external refresh with a
  // different query — issue exactly one replace request. The dispatch sets the
  // requestSignature synchronously, so this self-stabilizes. It deliberately
  // does NOT refire on errors (the signature still matches): no auto-retry.
  useEffect(() => {
    if (!matchesQuery(entry?.requestSignature, params, queryParams)) {
      dispatch(postRequest(dataKey, {}, params, queryParams));
    }
  }, [dispatch, dataKey, params, queryParams, entry?.requestSignature]);

  // Never render data of a different query (e.g. completed items while the open
  // list is still loading after a state switch).
  const dataValid = matchesQuery(entry?.dataSignature, params, queryParams);
  const data = dataValid ? (entry?.data as CursorItemsResponse<WorkflowInstance>) : undefined;
  const error = entry?.postResponse !== undefined && entry.postResponse !== 200;

  const loadMore = useCallback(() => {
    if (!data?.NEXT_CURSOR || loadingReplace || loadingAppend) return;
    dispatch(
      postRequest(
        dataKey,
        {},
        params,
        buildQueryParams(search, data.NEXT_CURSOR),
        undefined,
        undefined,
        { append: true }
      )
    );
  }, [dispatch, dataKey, params, search, data?.NEXT_CURSOR, loadingReplace, loadingAppend]);

  // Manual retry (error buttons) — a plain replace request for the desired query.
  const reload = useCallback(() => {
    dispatch(postRequest(dataKey, {}, params, queryParams));
  }, [dispatch, dataKey, params, queryParams]);

  return {
    items: data?.ITEMS ?? [],
    loadingInitial: !dataValid && !error,
    loadingMore: !!loadingAppend,
    error,
    hasMore: data?.NEXT_CURSOR != null,
    loadMore,
    reload,
  };
};
