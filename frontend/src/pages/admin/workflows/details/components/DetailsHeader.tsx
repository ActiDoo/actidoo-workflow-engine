// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { WeDetailsTable } from '@/utils/components/WeDetailsTable';
import { WeStateCompletedIcon, WeStateErrorIcon } from '@/utils/components/WeStateIcon';
import { AdminWorkflowInstance } from '@/models/models';
import { useTranslation } from '@/i18n';

const AdminWorkflowDetailsHeader: React.FC<{ workflow?: AdminWorkflowInstance }> = props => {
  const { t } = useTranslation();
  const { workflow } = { ...props };
  return (
    <div className=" flex gap-16 items-start pb-2">
      <WeDetailsTable
        data={[
          { label: t('adminDetailsHeader.id'), content: workflow?.id },
          { label: t('adminDetailsHeader.name'), content: workflow?.name },
        ]}
      />
      <WeDetailsTable
        data={[
          { label: t('adminDetailsHeader.title'), content: workflow?.title },
          {
            label: t('adminDetailsHeader.subtitle'),
            content: workflow?.subtitle,
          },
        ]}
      />
      <WeDetailsTable
        data={[
          {
            label: t('adminDetailsHeader.isCompleted'),
            content: workflow?.is_completed ? <WeStateCompletedIcon /> : '',
          },
          {
            label: t('adminDetailsHeader.hasError'),
            content: workflow?.has_task_in_error_state ? <WeStateErrorIcon /> : '',
          },
        ]}
      />
      <WeDetailsTable
        data={[
          {
            label: t('adminDetailsHeader.createdBy'),
            content: workflow?.created_by ? <>{workflow.created_by.full_name}</> : '',
          },
        ]}
      />
    </div>
  );
};

export default AdminWorkflowDetailsHeader;
