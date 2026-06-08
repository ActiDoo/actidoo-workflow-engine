// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchPost, StringDict } from '@/ui5-components';
import { getApiUrl } from '@/services/ApiService';
import { WorkflowInstance, WorkflowState } from '@/models/models';

const PAGE_SIZE = 100;

interface WorkflowInstancesPage {
  ITEMS: WorkflowInstance[];
  COUNT: number;
  NEXT_CURSOR?: string | null;
}

export interface UseInfiniteWorkflowInstancesResult {
  items: WorkflowInstance[];
  count: number;
  loadingInitial: boolean;
  loadingMore: boolean;
  error: boolean;
  hasMore: boolean;
  loadMore: () => void;
  reload: () => void;
}

/** Keyset-paginated loader for the "Aufgaben" sidebar list (infinite scroll + backend search). */
export const useInfiniteWorkflowInstances = (
  state: WorkflowState,
  search: string
): UseInfiniteWorkflowInstancesResult => {
  const [items, setItems] = useState<WorkflowInstance[]>([]);
  const [count, setCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(false);

  // requestIdRef invalidates stale responses after a reset; loadingRef guards loadMore.
  const requestIdRef = useRef(0);
  const loadingRef = useRef(false);

  const fetchPage = useCallback(
    async (cursor: string | null, isInitial: boolean) => {
      loadingRef.current = true;
      const requestId = ++requestIdRef.current;

      if (isInitial) setLoadingInitial(true);
      else setLoadingMore(true);
      setError(false);

      const queryParams: StringDict = { limit: String(PAGE_SIZE) };
      if (search) queryParams.search = search;
      if (cursor) queryParams.cursor = cursor;

      try {
        const url = getApiUrl(`user/workflow_instances_with_tasks/${state}`, queryParams);
        const { response, data } = await fetchPost(url, {});

        if (requestId !== requestIdRef.current) return; // superseded by a newer query

        if (response !== 200 || !data) {
          setError(true);
          return;
        }

        const page = data as WorkflowInstancesPage;
        setCount(page.COUNT ?? 0);
        setNextCursor(page.NEXT_CURSOR ?? null);
        setItems(prev => {
          if (isInitial) return page.ITEMS ?? [];
          const seen = new Set(prev.map(i => i.id));
          const fresh = (page.ITEMS ?? []).filter(i => !seen.has(i.id));
          return [...prev, ...fresh];
        });
      } catch {
        if (requestId === requestIdRef.current) setError(true);
      } finally {
        // Only the current request clears the flags (a stale one must not).
        if (requestId === requestIdRef.current) {
          setLoadingInitial(false);
          setLoadingMore(false);
          loadingRef.current = false;
        }
      }
    },
    [state, search]
  );

  // Reset + reload on state / (debounced) search change.
  useEffect(() => {
    setItems([]);
    setCount(0);
    setNextCursor(null);
    void fetchPage(null, true);
  }, [fetchPage]);

  const loadMore = useCallback(() => {
    if (loadingRef.current || !nextCursor) return;
    void fetchPage(nextCursor, false);
  }, [fetchPage, nextCursor]);

  const reload = useCallback(() => {
    setItems([]);
    setCount(0);
    setNextCursor(null);
    void fetchPage(null, true);
  }, [fetchPage]);

  return {
    items,
    count,
    loadingInitial,
    loadingMore,
    error,
    hasMore: nextCursor != null,
    loadMore,
    reload,
  };
};
