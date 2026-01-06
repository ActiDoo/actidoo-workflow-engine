// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { Icon, IconDesign } from '@ui5/webcomponents-react';
import React from 'react';
import '@ui5/webcomponents-icons/dist/cancel';
import '@ui5/webcomponents-icons/dist/status-negative';
import '@ui5/webcomponents-icons/dist/status-positive';
import '@ui5/webcomponents-icons/dist/play';
import { TaskItem } from '@/models/models';
import { useTranslation } from '@/i18n';

export const WeStateCanceledIcon: React.FC<{ title?: string }> = ({ title }) => {
  return <Icon name="cancel" design={IconDesign.Neutral} title={title} />;
};
export const WeStateErrorIcon: React.FC<{ title?: string }> = ({ title }) => {
  return <Icon name="status-negative" design={IconDesign.Negative} title={title} />;
};
export const WeStateCompletedIcon: React.FC<{ title?: string }> = ({ title }) => {
  return <Icon name="status-positive" design={IconDesign.Positive} title={title} />;
};
export const WeStateReadyIcon: React.FC<{ title?: string }> = ({ title }) => {
  return <Icon name="play" title={title} />;
};

export const WeTaskStateIcons: React.FC<{
  data: TaskItem;
  showEmptyCircle?: boolean;
  displayLabel?: boolean;
}> = props => {
  const { t } = useTranslation();
  const completedLabel = t('common.labels.completed');
  const errorLabel = t('common.labels.error');
  const readyLabel = t('common.labels.ready');
  const canceledLabel = t('common.labels.canceled');
  const noneLabel = t('common.labels.none');
  return (
    <span className="inline-flex items-center gap-2">
      {props.data.state_completed ? (
        <>
          <WeStateCompletedIcon title={completedLabel} />
          {props.displayLabel ? completedLabel : null}
        </>
      ) : null}
      {props.data.state_error ? (
        <>
          <WeStateErrorIcon title={errorLabel} />
          {props.displayLabel ? errorLabel : null}
        </>
      ) : null}
      {props.data.state_ready ? (
        <>
          <WeStateReadyIcon title={readyLabel} />
          {props.displayLabel ? readyLabel : null}
        </>
      ) : null}
      {props.data.state_cancelled ? (
        <>
          <WeStateCanceledIcon title={canceledLabel} />
          {props.displayLabel ? canceledLabel : null}
        </>
      ) : null}
      {props.showEmptyCircle &&
      !props.data.state_completed &&
      !props.data.state_error &&
      !props.data.state_cancelled &&
      !props.data.state_ready ? (
        <>
          <span className="w-4 h-4 rounded-full border-solid border inline-block"></span>{' '}
          {props.displayLabel ? noneLabel : null}
        </>
      ) : null}
    </span>
  );
};
