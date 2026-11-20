// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { ReactElement } from 'react';
import { useTranslation } from '@/i18n';
import { errorId, FieldErrorProps } from '@rjsf/utils';

const CustomFieldErrorTemplate = (props: FieldErrorProps): ReactElement | null => {
  const { t } = useTranslation();
  const { errors = [], fieldPathId, uiSchema } = props;
  if (errors.length === 0) {
    return null;
  }

  const id = errorId(fieldPathId);
  const upload = uiSchema?.['ui:field'];
  const normalizedErrors = errors.map(error => {
    if (upload === 'AttachmentSingle' && error === 'must be object')
      return t('formErrors.attachmentRequired');
    if (upload === 'AttachmentMulti' && error === t('formErrors.minItemsOne'))
      return t('formErrors.attachmentRequired');
    return error;
  });

  return (
    // copied html from packages/bootstrap-4/src/FieldErrorTemplate/FieldErrorTemplate.tsx:
    <ul id={id} className="list-group">
      {normalizedErrors.map((error, i) => (
        <li key={i} className="list-group-item border-0 m-0 p-0">
          <small className="m-0 text-danger">{error}</small>
        </li>
      ))}
    </ul>
  );
};

export default CustomFieldErrorTemplate;
