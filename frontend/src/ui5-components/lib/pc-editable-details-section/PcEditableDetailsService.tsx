// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  PcDetailsSectionItem,
  PcDetailsSectionItemType,
  PcDetailsSectionTransformType,
} from '@/ui5-components/lib/pc-editable-details-section/models/PcEditableDetailsSectionModels';
import { ValueState } from '@ui5/webcomponents-react';
import { HTTPValidationError } from '@/ui5-components/models/models';
import _ from 'lodash';

function resolvePath<T>(object: T, key: string): any {
  return _.get(object, key.split('.'), undefined);
}
export function setPath<T>(object: T, key: string, value: any): T {
  const copy = object ? structuredClone(object) : {};
  return _.set(copy as object, key, value) as T;
}
export function getValueAsString<T>(item: PcDetailsSectionItem, data: T | undefined): string {
  let val: string | undefined = resolvePath(data, item.key) as string | undefined;
  if (item.transform === PcDetailsSectionTransformType.DATE) {
    val = val ? new Date(val).toLocaleString() : '';
  }
  return val !== undefined && val !== null ? val : '';
}
export function getValueAsNumber<T>(
  item: PcDetailsSectionItem,
  data: T | undefined
): number | undefined {
  const val: number | undefined = resolvePath(data, item.key) as number | undefined;
  return val !== undefined && val !== null ? val : undefined;
}

export function getValueAsArray<T>(item: PcDetailsSectionItem, data: T | undefined): string[] {
  const val: string[] | undefined = resolvePath(data, item.key) as string[] | undefined;
  return val ?? [];
}

export function getValueAsBoolean<T>(item: PcDetailsSectionItem, data: T | undefined): boolean {
  const val: boolean | undefined = resolvePath(data, item.key) as boolean | undefined;
  return val ?? false;
}

export function getValueState<T>(
  item: PcDetailsSectionItem,
  dataMap: T | undefined,
  validationError?: HTTPValidationError
): ValueState {
  if (
    validationError?.detail?.some(e => e.loc[1] === item.key) ||
    (item.required && !hasData(item, dataMap))
  ) {
    return ValueState.Error;
  }
  return ValueState.None;
}

export function getValueStateMassage(
  item: PcDetailsSectionItem,
  validationError?: HTTPValidationError
): string {
  return validationError?.detail?.find(e => e.loc[1] === item.key)?.msg ?? 'Required';
}

export function hasData<T>(item: PcDetailsSectionItem, dataMap: T | undefined): boolean {
  const itemData = dataMap ? resolvePath(dataMap, item.key) : undefined;
  let hasData = dataMap ? !!itemData : false;
  if (item.type === PcDetailsSectionItemType.MULTI_INPUT && itemData && dataMap) {
    hasData = (itemData as string[])?.length > 0;
  }
  return hasData;
}

export function getErrorMessage(
  loadResponse: number | undefined,
  deleteResponse: number | undefined,
  saveResponse: number | undefined,
  validationError: HTTPValidationError | undefined
): string {
  if (validationError) return 'There is a validation error. Improve your inputs and try again.';
  if (loadResponse)
    return 'An error has occurred while loading the data. Reload the page to try again.';
  if (deleteResponse) return 'An error has occurred while deleting the data. Please try again.';
  if (saveResponse) return 'An error has occurred while saving the data. Please try again.';
  return 'There was a problem. Please try again.';
}
