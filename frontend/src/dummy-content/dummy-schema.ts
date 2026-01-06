// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { RJSFSchema } from '@rjsf/utils';

export const fileSchema: RJSFSchema = {
  title: 'Files',
  type: 'object',
  properties: {
    singlefile: {
      readOnly: false,
      type: 'string',
      format: 'data-url',
      title: 'Single file',
    },
    files: {
      readOnly: false,
      type: 'array',
      title: 'Multiple files',
      items: {
        type: 'string',
        format: 'data-url',
      },
    },
  },
};
export const fileUiSchema = {
  'ui:layout': { Row_1xia6dx: ['files'], Row_324: ['singlefile'] },
};

export const dropdownSchema: RJSFSchema = {
  title: 'Drop Down Search',
  type: 'object',
  properties: {
    single: {
      readOnly: false,
      type: 'string',
      title: 'Select one',
    },
    multi: {
      readOnly: false,
      type: 'array',
      title: 'Multiple Select',
      items: {
        type: 'string',
      },
    },
  },
};
export const dropdownUiSchema = {
  'ui:layout': { Row_1xia6dx: ['single'], Row_1x2ia6dx: ['multi'] },
  single: { 'ui:widget': 'dropdownSearch' },
  multi: { 'ui:widget': 'dropdownSearch' },
};
