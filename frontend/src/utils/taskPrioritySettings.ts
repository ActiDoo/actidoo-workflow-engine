// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { WorkflowDeadline } from '@/models/models';

export type TaskPriorityLevel = 'normal' | 'urgency' | 'critical';

const getDateTimeValue = (value?: string | Date | null): number | undefined => {
  if (!value) return undefined;
  const date = new Date(value);
  const time = date.getTime();
  return Number.isNaN(time) ? undefined : time;
};

const normalizeDeadlineLevel = (level?: string | null): TaskPriorityLevel => {
  if (level === 'critical' || level === 'urgency') return level;
  return 'normal';
};

const priorityRank: Record<TaskPriorityLevel, 0 | 1 | 2> = {
  normal: 0,
  urgency: 1,
  critical: 2,
};

export const getTaskPriorityMeta = (params: {
  deadline?: WorkflowDeadline | null;
  createdAt?: string | Date | null;
  priorityDate?: string | Date | null;
}): { level: TaskPriorityLevel; priority: 0 | 1 | 2; referenceTime: number } => {
  const level = normalizeDeadlineLevel(params.deadline?.level);
  const referenceTime =
    getDateTimeValue(
      level === 'critical' ? params.deadline?.critical_at : params.deadline?.urgency_at
    ) ??
    getDateTimeValue(params.priorityDate ?? params.createdAt) ??
    0;

  return {
    level,
    priority: priorityRank[level],
    referenceTime,
  };
};
