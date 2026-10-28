// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';

const valueClassName = (value: unknown): string => {
  if (value === null) return 'text-neutral-500';
  if (typeof value === 'string') return 'text-red-700';
  return 'text-blue-700';
};

const JsonNode: React.FC<{ name: string; value: unknown }> = ({ name, value }) => {
  const label = <span className="text-purple-800">{name}: </span>;

  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value);
    return (
      <details>
        <summary className="cursor-pointer">
          {label}
          <span className="text-neutral-500">
            {Array.isArray(value) ? `Array(${entries.length})` : `{…} ${entries.length}`}
          </span>
        </summary>
        <div className="ml-4">
          {entries.map(([key, child]) => (
            <JsonNode key={key} name={key} value={child} />
          ))}
        </div>
      </details>
    );
  }

  return (
    <div className="ml-4">
      {label}
      <span className={valueClassName(value)}>{JSON.stringify(value)}</span>
    </div>
  );
};

export const WeJsonTree: React.FC<{ data: object }> = ({ data }) => (
  <div className="mt-2 font-mono text-sm p-2 max-h-[30rem] overflow-auto border border-solid border-[color:var(--sapField_BorderColor)] rounded-[var(--sapField_BorderCornerRadius)] bg-[var(--sapField_Background)]">
    {Object.entries(data).map(([key, value]) => (
      <JsonNode key={key} name={key} value={value} />
    ))}
  </div>
);
