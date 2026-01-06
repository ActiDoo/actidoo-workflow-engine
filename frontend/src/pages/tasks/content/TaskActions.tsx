// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { useTranslation } from '@/i18n';

export interface TaskActionsProps {
  disabled?: boolean;
  onReset: () => void;
}

export const TaskActions: React.FC<TaskActionsProps> = props => {
  const { t } = useTranslation();
  return (
    <>
      <div className="flex flex-row flex-wrap gap-2 mt-16 ">
        <button
          disabled={!!props.disabled}
          type="button"
          className="btn btn-secondary min-w-[200px] max-h-[38px]"
          onClick={props.onReset}>
          {t('taskActions.reset')}
        </button>
        <div className="flex-1"></div>
        <div className="flex flex-column gap-2">
          <button
            disabled={!!props.disabled}
            type="submit"
            className="btn btn-primary m-0 max-h-[38px]">
            {t('taskActions.submit')}
          </button>
        </div>
      </div>
    </>
  );
};
