// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';

import { State } from '@/store';
import { postRequest, resetStateForKey } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import { useSelectUiLoading } from '@/store/ui/selectors';

// Store glue for the four form-template endpoints (all POST). Components stay presentational.
export const useFormTemplates = (taskId?: string) => {
  const dispatch = useDispatch();

  const listEntry = useSelector((state: State) => state.data[WeDataKey.FORM_TEMPLATES_LIST]);
  const saveEntry = useSelector((state: State) => state.data[WeDataKey.FORM_TEMPLATE_SAVE]);
  const previewEntry = useSelector((state: State) => state.data[WeDataKey.FORM_TEMPLATE_PREVIEW]);
  const resolveEntry = useSelector((state: State) => state.data[WeDataKey.FORM_TEMPLATE_RESOLVE]);
  const deleteEntry = useSelector((state: State) => state.data[WeDataKey.FORM_TEMPLATE_DELETE]);

  const fetchList = useCallback(() => {
    if (!taskId) return;
    dispatch(postRequest(WeDataKey.FORM_TEMPLATES_LIST, { task_id: taskId }));
  }, [dispatch, taskId]);

  const saveTemplate = useCallback(
    (name: string, data: object) => {
      if (!taskId) return;
      dispatch(
        postRequest(WeDataKey.FORM_TEMPLATE_SAVE, {
          task_id: taskId,
          template_name: name,
          template_data: data,
        })
      );
    },
    [dispatch, taskId]
  );

  const previewTemplate = useCallback(
    (data: object) => {
      if (!taskId) return;
      dispatch(
        postRequest(WeDataKey.FORM_TEMPLATE_PREVIEW, { task_id: taskId, template_data: data })
      );
    },
    [dispatch, taskId]
  );

  const resetPreview = useCallback(() => {
    dispatch(resetStateForKey(WeDataKey.FORM_TEMPLATE_PREVIEW));
  }, [dispatch]);

  const resolveTemplate = useCallback(
    (templateId: string) => {
      if (!taskId) return;
      dispatch(
        postRequest(WeDataKey.FORM_TEMPLATE_RESOLVE, { task_id: taskId, template_id: templateId })
      );
    },
    [dispatch, taskId]
  );

  const deleteTemplate = useCallback(
    (templateId: string) => {
      dispatch(postRequest(WeDataKey.FORM_TEMPLATE_DELETE, { template_id: templateId }));
    },
    [dispatch]
  );

  const resetResolve = useCallback(() => {
    dispatch(resetStateForKey(WeDataKey.FORM_TEMPLATE_RESOLVE));
  }, [dispatch]);

  return {
    templates: listEntry?.data?.templates ?? [],
    listLoading: useSelectUiLoading(WeDataKey.FORM_TEMPLATES_LIST, 'POST'),
    fetchList,

    saveEntry,
    saveLoading: useSelectUiLoading(WeDataKey.FORM_TEMPLATE_SAVE, 'POST'),
    saveTemplate,

    previewResult: previewEntry?.data,
    previewLoading: useSelectUiLoading(WeDataKey.FORM_TEMPLATE_PREVIEW, 'POST'),
    previewTemplate,
    resetPreview,

    resolveEntry,
    resolved: resolveEntry?.data,
    resolveLoading: useSelectUiLoading(WeDataKey.FORM_TEMPLATE_RESOLVE, 'POST'),
    resolveTemplate,
    resetResolve,

    deleteEntry,
    deleteLoading: useSelectUiLoading(WeDataKey.FORM_TEMPLATE_DELETE, 'POST'),
    deleteTemplate,
  };
};
