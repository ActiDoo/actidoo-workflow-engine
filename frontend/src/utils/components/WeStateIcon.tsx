import { Icon, IconDesign } from '@ui5/webcomponents-react';
import React from 'react';
import '@ui5/webcomponents-icons/dist/cancel';
import '@ui5/webcomponents-icons/dist/status-negative';
import '@ui5/webcomponents-icons/dist/status-positive';
import '@ui5/webcomponents-icons/dist/play';
import { TaskItem } from '@/models/models';

export const WeStateCanceledIcon: React.FC = () => {
  return <Icon name="cancel" design={IconDesign.Neutral} title="cancleed" />;
};
export const WeStateErrorIcon: React.FC = () => {
  return <Icon name="status-negative" design={IconDesign.Negative} title="error" />;
};
export const WeStateCompletedIcon: React.FC = () => {
  return <Icon name="status-positive" design={IconDesign.Positive} title="completed" />;
};
export const WeStateReadyIcon: React.FC = () => {
  return <Icon name="play" title="ready" />;
};

export const WeTaskStateIcons: React.FC<{
  data: TaskItem;
  showEmptyCircle?: boolean;
  displayLabel?: boolean;
}> = props => {
  return (
    <span className="inline-flex items-center gap-2">
      {props.data.state_completed ? (
        <>
          <WeStateCompletedIcon />
          {props.displayLabel ? 'completed' : null}
        </>
      ) : null}
      {props.data.state_error ? (
        <>
          <WeStateErrorIcon />
          {props.displayLabel ? 'error' : null}
        </>
      ) : null}
      {props.data.state_ready ? (
        <>
          <WeStateReadyIcon />
          {props.displayLabel ? 'ready' : null}
        </>
      ) : null}
      {props.data.state_cancelled ? (
        <>
          <WeStateCanceledIcon />
          {props.displayLabel ? 'canceled' : null}
        </>
      ) : null}
      {props.showEmptyCircle &&
      !props.data.state_completed &&
      !props.data.state_error &&
      !props.data.state_cancelled &&
      !props.data.state_ready ? (
        <>
          <span className="w-4 h-4 rounded-full border-solid border inline-block"></span>{' '}
          {props.displayLabel ? 'none' : null}
        </>
      ) : null}
    </span>
  );
};
