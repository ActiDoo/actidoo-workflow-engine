// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { createContext, useContext } from 'react';
import { escapeRegExp } from 'lodash';

export const ObjectDataContext = createContext<{ formData: any; schema: any } | undefined>(
  undefined
);

export const getPropertyPath = (id: string, uiPath: string[]): Array<string | number> => {
  const match = new RegExp(`^root_${uiPath.map(escapeRegExp).join('_(\\d+)_')}$`).exec(id);
  if (!match) return uiPath;
  const rows = match.slice(1).map(Number);
  return uiPath.flatMap((key, i) => (i < rows.length ? [key, rows[i]] : [key]));
};

export const useDependencyValues = (
  dependsOn: string[] | undefined,
  formContext: any
): unknown[] => {
  const scope = useContext(ObjectDataContext);
  return (dependsOn ?? []).map(dep =>
    scope?.schema?.properties && dep in scope.schema.properties
      ? scope.formData?.[dep] ?? null
      : formContext?.formData?.[dep] ?? null
  );
};
