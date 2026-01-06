// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { AdminGraphInstance } from '@/models/models';

type WF = {
  title: string;
  dates: Date[];
};

/**
 * this function takes the wf_instance objects, and takes out the name, and the created_at attributes
 * @returns an array of dictionaries containing the name, and a list of dates
 */
export function filterWorkflows(wf_instances: AdminGraphInstance[] = []) {
  const wfMap: Record<string, { title: string; dates: Date[] }> = {};
  wf_instances.forEach(wf => {
    const name = wf.name!;
    const title = wf.title!;
    const date: Date = new Date(wf.created_at!);
    if (!wfMap[name]) {
      wfMap[name] = {
        title,
        dates: [date],
      };
    } else {
      wfMap[name].dates.push(date);
    }
  });

  return Object.values(wfMap).map(({ title, dates }) => ({
    title,
    dates,
  }));
}

export function mergeByTitle(workflows: WF[]): WF[] {
  const mergedMap = new Map<string, WF>();

  for (const wf of workflows) {
    const existing = mergedMap.get(wf.title);

    if (existing) {
      mergedMap.set(wf.title, {
        title: wf.title,
        dates: [...existing.dates, ...wf.dates],
      });
    } else {
      mergedMap.set(wf.title, { ...wf });
    }
  }

  return Array.from(mergedMap.values());
}
