// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import { debounce } from 'lodash';
import { fetchPost } from '@/ui5-components';
import { getApiUrl } from '@/services/ApiService';
import { PcValueLabelItem } from '@/models/models';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';
import { stripAttachmentPayload } from '@/rjsf-customs/custom-fields/multiFileField/attachments';

export const PROPERTY_OPTIONS_DEBOUNCE_MS = 300;

export interface PropertyOptionsPage {
  options: PcValueLabelItem[];
  has_more?: boolean;
  next_offset?: number | null;
}

export interface UsePropertyOptionsParams {
  taskId: string | undefined;
  propertyPath: string[] | undefined;
  search: string;
  includeValue: unknown;
  formData: unknown;
}

export interface UsePropertyOptionsResult {
  options: PcValueLabelItem[] | undefined;
  isLoading: boolean;
  hasMore: boolean;
  reload: () => void;
  cancelReload: () => void;
  loadMore: () => void;
  clear: () => void;
}

const mergeOptions = (
  current: PcValueLabelItem[] | undefined,
  incoming: PcValueLabelItem[]
): PcValueLabelItem[] => {
  const known = new Set((current ?? []).map(o => o.value));
  return [...(current ?? []), ...incoming.filter(o => !known.has(o.value))];
};

export const usePropertyOptions = (params: UsePropertyOptionsParams): UsePropertyOptionsResult => {
  const [options, setOptions] = useState<PcValueLabelItem[] | undefined>(undefined);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const dispatch = useDispatch();

  const paramsRef = useRef(params);
  paramsRef.current = params;
  const requestIdRef = useRef(0);
  const loadingMoreRef = useRef(false);

  const fetchPage = useCallback(
    async (offset: number): Promise<PropertyOptionsPage | undefined> => {
      const { taskId, propertyPath, search, includeValue, formData } = paramsRef.current;
      if (!propertyPath) {
        return undefined;
      }
      if (!taskId) {
        return { options: [], has_more: false, next_offset: null };
      }
      const res = await fetchPost(getApiUrl('user/search_property_options'), {
        task_id: taskId,
        property_path: propertyPath,
        search,
        include_value: includeValue,
        form_data: stripAttachmentPayload(formData),
        offset,
      });
      return res.data as PropertyOptionsPage;
    },
    []
  );

  const reportError = useCallback(() => {
    dispatch(addToast(<WeToastContent text={`Could not load options. Please try again.`} />));
  }, [dispatch]);

  const loadFirstPage = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    loadingMoreRef.current = false;
    setIsLoading(true);
    try {
      const page = await fetchPage(0);
      if (requestId !== requestIdRef.current) return;
      setOptions(page?.options);
      setNextOffset(page?.has_more ? page.next_offset ?? null : null);
    } catch {
      if (requestId !== requestIdRef.current) return;
      setOptions([]);
      setNextOffset(null);
      reportError();
    } finally {
      if (requestId === requestIdRef.current) setIsLoading(false);
    }
  }, [fetchPage, reportError]);

  const reload = useMemo(
    () =>
      debounce(() => {
        loadFirstPage().catch(() => undefined);
      }, PROPERTY_OPTIONS_DEBOUNCE_MS),
    [loadFirstPage]
  );

  useEffect(() => {
    return () => {
      reload.cancel();
    };
  }, [reload]);

  const loadMore = useCallback(() => {
    if (nextOffset === null || isLoading || loadingMoreRef.current) return;
    const requestId = requestIdRef.current;
    loadingMoreRef.current = true;
    setIsLoading(true);
    (async () => {
      try {
        const page = await fetchPage(nextOffset);
        if (requestId !== requestIdRef.current) return;
        setOptions(current => mergeOptions(current, page?.options ?? []));
        setNextOffset(page?.has_more ? page.next_offset ?? null : null);
      } catch {
        if (requestId !== requestIdRef.current) return;
        setNextOffset(null);
        reportError();
      } finally {
        if (requestId === requestIdRef.current) {
          loadingMoreRef.current = false;
          setIsLoading(false);
        }
      }
    })().catch(() => undefined);
  }, [fetchPage, isLoading, nextOffset, reportError]);

  const clear = useCallback(() => {
    requestIdRef.current += 1;
    reload.cancel();
    loadingMoreRef.current = false;
    setOptions([]);
    setNextOffset(null);
    setIsLoading(false);
  }, [reload]);

  return {
    options,
    isLoading,
    hasMore: nextOffset !== null,
    reload,
    cancelReload: reload.cancel,
    loadMore,
    clear,
  };
};
