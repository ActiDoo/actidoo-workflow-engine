// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

export enum PcDetailsSectionItemType {
  INPUT = 1,
  TEXTAREA,
  CHECKBOX,
  MULTI_INPUT,
  SELECT,
  STEP_INPUT,
}
export enum PcDetailsSectionTransformType {
  DATE = 1,
}

export interface PcDetailsSectionItem {
  label: string;
  key: string;
  description?: string;
  type?: PcDetailsSectionItemType;
  options?: PcDetailsItemOption[];
  transform?: PcDetailsSectionTransformType;
  required?: boolean;
  readonly?: boolean;
  visible?: boolean;
}
export interface PcDetailsItemOption {
  value: any;
  label: string;
}
