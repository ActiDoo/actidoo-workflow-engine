// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { useCallback, useEffect, useRef } from 'react';
import _ from 'lodash';
import { fetchPost } from '@/ui5-components';
import { getApiUrl } from '@/services/ApiService';
import { ROW_ID_KEY } from '@/models/models';
import { isDynamicListUiItems } from '@/utils/rowIdentity';
import { stripAttachmentPayload } from '@/rjsf-customs/custom-fields/multiFileField/attachments';

const CHANGE_FUNCTION_DEBOUNCE_MS = 300;

type Path = Array<string | number>;

interface FormChange {
  path: Path;
  value: unknown;
}

const previousRow = (row: any, previousRows: unknown, index: number): unknown => {
  if (!Array.isArray(previousRows)) return undefined;
  const rowId = row?.[ROW_ID_KEY];
  return rowId
    ? previousRows.find(candidate => candidate?.[ROW_ID_KEY] === rowId)
    : previousRows[index];
};

const collectChangedTriggers = (
  uiSchema: any,
  data: any,
  previous: any,
  path: Path = []
): Path[] => {
  const changed: Path[] = [];
  for (const [key, ui] of Object.entries<any>(uiSchema ?? {})) {
    if (key.startsWith('ui:') || typeof ui !== 'object' || ui === null) continue;
    if (ui['ui:changeFunction'] && !_.isEqual(data?.[key] ?? null, previous?.[key] ?? null)) {
      changed.push([...path, key]);
    }
    if (isDynamicListUiItems(ui.items) && Array.isArray(data?.[key])) {
      data[key].forEach((row: unknown, index: number) => {
        changed.push(
          ...collectChangedTriggers(ui.items, row, previousRow(row, previous?.[key], index), [
            ...path,
            key,
            index,
          ])
        );
      });
    }
  }
  return changed;
};

const allowsNull = (schema: any, path: Path): boolean => {
  let node = schema;
  for (const part of path) {
    node = typeof part === 'number' ? node?.items : node?.properties?.[part];
  }
  return Array.isArray(node?.type) && node.type.includes('null');
};

const applyFormChanges = (schema: any, data: any, changes: FormChange[]): any => {
  const next = _.cloneDeep(data ?? {});
  for (const { path, value } of changes) {
    if (path.length > 1 && !_.isObject(_.get(next, path.slice(0, -1)))) continue;
    if (value === null && !allowsNull(schema, path)) {
      _.unset(next, path);
    } else {
      _.set(next, path, value);
    }
  }
  return next;
};

interface UseChangeFunctionsParams {
  taskId: string | undefined;
  schema: any;
  uiSchema: any;
  formData: any;
  onChange: (formData: any) => void;
}

interface UseChangeFunctionsResult {
  handleChange: (formData: any) => void;
  whenSettled: () => Promise<any> | undefined;
}

export const useChangeFunctions = (params: UseChangeFunctionsParams): UseChangeFunctionsResult => {
  const paramsRef = useRef(params);
  paramsRef.current = params;
  const latestRef = useRef(params.formData);
  const pendingRef = useRef(new Map<string, Path>());
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const runningRef = useRef<Promise<void>>(Promise.resolve());
  const runCountRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    latestRef.current = params.formData;
  }, [params.formData]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearTimeout(timerRef.current);
    };
  }, []);

  const run = useCallback(async (): Promise<void> => {
    while (pendingRef.current.size > 0 && mountedRef.current) {
      const [key, path] = pendingRef.current.entries().next().value as [string, Path];
      pendingRef.current.delete(key);
      const { taskId, schema, onChange } = paramsRef.current;
      const sent = latestRef.current;
      try {
        const res = await fetchPost(getApiUrl('user/form_change'), {
          task_id: taskId,
          property_path: path,
          form_data: stripAttachmentPayload(sent),
        });
        const changes = (res.data as { changes?: FormChange[] } | undefined)?.changes ?? [];
        const isStale =
          paramsRef.current.taskId !== taskId ||
          pendingRef.current.has(key) ||
          !_.isEqual(_.get(sent, path) ?? null, _.get(latestRef.current, path) ?? null);
        if (!mountedRef.current || isStale || changes.length === 0) continue;
        latestRef.current = applyFormChanges(schema, latestRef.current, changes);
        onChange(latestRef.current);
      } catch (error) {
        console.error('change_function request failed', error);
      }
    }
  }, []);

  const flush = useCallback((): void => {
    clearTimeout(timerRef.current);
    timerRef.current = undefined;
    runCountRef.current += 1;
    runningRef.current = runningRef.current.then(run).finally(() => {
      runCountRef.current -= 1;
    });
  }, [run]);

  const handleChange = useCallback(
    (formData: any): void => {
      const { taskId, uiSchema } = paramsRef.current;
      const previous = latestRef.current;
      latestRef.current = formData;
      if (!taskId) return;
      const changed = collectChangedTriggers(uiSchema, formData, previous);
      if (changed.length === 0) return;
      changed.forEach(path => pendingRef.current.set(JSON.stringify(path), path));
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(flush, CHANGE_FUNCTION_DEBOUNCE_MS);
    },
    [flush]
  );

  const whenSettled = useCallback((): Promise<any> | undefined => {
    if (timerRef.current !== undefined) flush();
    if (runCountRef.current === 0) return undefined;
    return runningRef.current.then(() => latestRef.current);
  }, [flush]);

  return { handleChange, whenSettled };
};
