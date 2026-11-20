// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { createContext, useContext } from 'react';
import { escapeRegExp } from 'lodash';

interface ObjectDataScope {
  formData: any;
  schema: any;
  parent?: ObjectDataScope;
}

export const ObjectDataContext = createContext<ObjectDataScope | undefined>(undefined);

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
  return (dependsOn ?? []).map(dep => {
    for (let current = scope; current; current = current.parent) {
      if (Object.prototype.hasOwnProperty.call(current.schema?.properties ?? {}, dep)) {
        return current.formData?.[dep] ?? null;
      }
    }
    return formContext?.formData?.[dep] ?? null;
  });
};
