// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

export interface TaskPrioritySettings {
  enabled: boolean;
  urgentHours: number;
  criticalHours: number;
}

export const DEFAULT_TASK_PRIORITY_SETTINGS: TaskPrioritySettings = {
  enabled: true,
  urgentHours: 7 * 24,
  criticalHours: 14 * 24,
};

export const TASK_PRIORITY_SETTINGS_STORAGE_KEY = 'wfe.taskPrioritySettings';
export const TASK_PRIORITY_SETTINGS_CHANGED_EVENT = 'wfe-task-priority-settings-changed';

const toPositiveInteger = (value: unknown, fallback: number): number => {
  const parsed = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return Math.max(1, Math.round(parsed));
};

export const normalizeTaskPrioritySettings = (
  value: Partial<TaskPrioritySettings> = {}
): TaskPrioritySettings => {
  const urgentHours = toPositiveInteger(
    value.urgentHours,
    DEFAULT_TASK_PRIORITY_SETTINGS.urgentHours
  );
  const criticalHours = toPositiveInteger(
    value.criticalHours,
    DEFAULT_TASK_PRIORITY_SETTINGS.criticalHours
  );

  return {
    enabled: value.enabled ?? DEFAULT_TASK_PRIORITY_SETTINGS.enabled,
    urgentHours,
    criticalHours: criticalHours > urgentHours ? criticalHours : urgentHours + 1,
  };
};

export const getTaskPrioritySettings = (): TaskPrioritySettings => {
  if (typeof window === 'undefined') return DEFAULT_TASK_PRIORITY_SETTINGS;

  try {
    const raw = window.localStorage.getItem(TASK_PRIORITY_SETTINGS_STORAGE_KEY);
    if (!raw) return DEFAULT_TASK_PRIORITY_SETTINGS;
    return normalizeTaskPrioritySettings(JSON.parse(raw) as Partial<TaskPrioritySettings>);
  } catch {
    return DEFAULT_TASK_PRIORITY_SETTINGS;
  }
};

export const saveTaskPrioritySettings = (settings: TaskPrioritySettings): TaskPrioritySettings => {
  const normalized = normalizeTaskPrioritySettings(settings);

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(TASK_PRIORITY_SETTINGS_STORAGE_KEY, JSON.stringify(normalized));
    window.dispatchEvent(
      new CustomEvent(TASK_PRIORITY_SETTINGS_CHANGED_EVENT, { detail: normalized })
    );
  }

  return normalized;
};
