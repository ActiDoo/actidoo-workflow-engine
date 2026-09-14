// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';

export const TASK_PRIORITY_URGENT_COLOR = '#FFA800';
export const TASK_PRIORITY_CRITICAL_COLOR = '#ED0A19';

type PriorityClockColor = typeof TASK_PRIORITY_URGENT_COLOR | typeof TASK_PRIORITY_CRITICAL_COLOR;

interface WePriorityClockProps {
  hour: number;
  minute?: number;
  color: PriorityClockColor;
  className?: string;
}

export const WePriorityClock: React.FC<WePriorityClockProps> = ({
  hour,
  minute = 0,
  color,
  className = 'inline-block h-[1em] w-[1em] shrink-0 align-[-0.12em]',
}) => {
  const minuteAngle = (minute / 60) * 360;
  const hourAngle = ((hour % 12) + minute / 60) * 30;

  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 110 110">
      <circle cx="55" cy="55" r="45" fill="white" stroke={color} strokeWidth="8" />
      <line
        x1="55"
        y1="55"
        x2="55"
        y2="20"
        stroke={color}
        strokeWidth="4"
        strokeLinecap="round"
        transform={`rotate(${minuteAngle} 55 55)`}
      />
      <line
        x1="55"
        y1="55"
        x2="55"
        y2="30"
        stroke={color}
        strokeWidth="6"
        strokeLinecap="round"
        transform={`rotate(${hourAngle} 55 55)`}
      />
    </svg>
  );
};
