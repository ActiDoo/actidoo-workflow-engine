// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { useTranslation } from '@/i18n';
import { BusyIndicator, Button, ButtonDesign } from '@ui5/webcomponents-react';
import { UserTask } from '@/models/models';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { WeDataKey } from '@/store/generic-data/setup';

export interface TaskActionsProps {
  task: UserTask;
  disabled?: boolean;
  onReset: () => void;
  onDelete: () => void;
}

export const TaskActions: React.FC<TaskActionsProps> = props => {
  const { t } = useTranslation();
  const { task } = props;
  const deleteWorkflowLoadState = useSelectUiLoading(WeDataKey.DELETE_WORKFLOW, 'POST');

  return (
    <>
      <div className="flex flex-row flex-wrap gap-2 w-full">
        <div className="flex flex-column gap-2">
          <button
            disabled={!!props.disabled}
            type="submit"
            className="btn btn-primary m-0 max-h-[38px]">
            {t('taskActions.submit')}
          </button>
        </div>
        <div className="flex-1"></div>
        <Button disabled={!!props.disabled} className="btn btn-secondary" onClick={props.onReset}>
          {t('taskActions.reset')}
        </Button>
        {task.can_delete_workflow ? (
          <BusyIndicator active={deleteWorkflowLoadState} delay={0} className="">
            <Button
              design={ButtonDesign.Negative}
              disabled={!!props.disabled}
              onClick={props.onDelete}>
              {t('taskActions.delete')}
            </Button>
          </BusyIndicator>
        ) : null}
      </div>
    </>
  );
};
