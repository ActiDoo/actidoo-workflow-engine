// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  DescriptionFieldProps,
  FormContextType,
  RJSFSchema,
  StrictRJSFSchema,
  getUiOptions,
} from '@rjsf/utils';
import Markdown from 'markdown-to-jsx';

/**
 * Custom DescriptionFieldTemplate that allows raw HTML in markdown descriptions.
 *
 * The default @rjsf/core RichDescription component sets `disableParsingRawHTML: true`
 * which was introduced in rjsf v6. This override restores HTML rendering support
 * for descriptions (e.g. in Camunda "text" form elements).
 */
export default function CustomDescriptionFieldTemplate<
  T = any,
  S extends StrictRJSFSchema = RJSFSchema,
  F extends FormContextType = any
>({ id, description, registry, uiSchema = {} }: DescriptionFieldProps<T, S, F>) {
  if (!description) {
    return null;
  }

  const { globalUiOptions } = registry;
  const uiOptions = getUiOptions<T, S, F>(uiSchema, globalUiOptions);

  if (uiOptions.enableMarkdownInDescription && typeof description === 'string') {
    return (
      <div id={id} className="mb-3">
        <Markdown>{description}</Markdown>
      </div>
    );
  }

  return (
    <div id={id} className="mb-3">
      {description}
    </div>
  );
}
