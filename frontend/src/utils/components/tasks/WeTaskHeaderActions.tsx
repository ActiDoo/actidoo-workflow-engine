// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';
import { BusyIndicator, BusyIndicatorSize, Button, ButtonDesign } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/synchronize';
import '@ui5/webcomponents-icons/dist/begin';
import '@ui5/webcomponents-icons/dist/cancel';
import '@ui5/webcomponents-icons/dist/user-edit';
import { useDispatch, useSelector } from 'react-redux';
import { postRequest } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import { TaskItem } from '@/models/models';
import { State } from '@/store';
import { handleResponse } from '@/services/HelperService';
import { useSelectUiLoading } from '@/store/ui/selectors';
import WeUserAutocomplete from '@/utils/components/WeUserAutocomplete';
import WeAlertDialog from '@/utils/components/WeAlertDialog';
import { useTranslation } from '@/i18n';

interface AdminTaskHeaderActionsProps {
  taskId: string;
  data: TaskItem | undefined;
}

const WeTaskHeaderActions: React.FC<AdminTaskHeaderActionsProps> = props => {
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string | undefined>(
    props.data?.assigned_user?.id
  );

  const executeErroneousTask = useSelector(
    (state: State) => state.data[WeDataKey.ADMIN_EXECUTE_ERRONEOUS_TASK]
  );
  const executeErroneousTaskLoadState = useSelectUiLoading(
    WeDataKey.ADMIN_EXECUTE_ERRONEOUS_TASK,
    'POST'
  );
  const assignTask = useSelector((state: State) => state.data[WeDataKey.ADMIN_ASSIGN_TASK]);
  const assignTaskLoadState = useSelectUiLoading(WeDataKey.ADMIN_ASSIGN_TASK, 'POST');
  const unassignTask = useSelector((state: State) => state.data[WeDataKey.ADMIN_UNASSIGN_TASK]);
  const unassignTaskLoadState = useSelectUiLoading(WeDataKey.ADMIN_UNASSIGN_TASK, 'POST');

  // A 409 carries a `code` that says why the retry did not succeed; the store
  // keeps the error body in `data`.
  const retryErrorText = (): string => {
    const errorBody = executeErroneousTask?.data as { code?: string } | undefined;
    switch (errorBody?.code) {
      case 'task_failed_again':
        return t('admin.taskExecutedFailedAgain');
      case 'follow_up_task_failed':
        return t('admin.taskExecutedFollowUpFailed');
      case 'workflow_instance_busy':
        return t('admin.taskExecutedBusy');
      case 'task_not_erroneous':
        return t('admin.taskExecutedAlreadyDone');
      default:
        return t('admin.taskExecutedError');
    }
  };

  // A retry changes more than the task it was aimed at: it may complete the
  // task and leave a later step of the workflow in error. Both hosts of these
  // buttons are refreshed, the single-task page and the workflow's task list.
  const reloadAfterRetry = (): void => {
    dispatch(postRequest(WeDataKey.ADMIN_ALL_TASKS, {}, undefined, { f_id: props.taskId }));
    const instanceId = props.data?.workflow_instance?.id;
    if (instanceId) {
      dispatch(
        postRequest(WeDataKey.ADMIN_TASKS_OF_WORKFLOW, {}, undefined, {
          f_workflow_instance___id: instanceId,
        })
      );
    }
  };

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.ADMIN_EXECUTE_ERRONEOUS_TASK,
      executeErroneousTask?.postResponse,
      t('admin.taskExecuted'),
      retryErrorText(),
      reloadAfterRetry,
      reloadAfterRetry
    );
  }, [executeErroneousTask?.postResponse]);

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.ADMIN_ASSIGN_TASK,
      assignTask?.postResponse,
      t('admin.assignUserSuccess'),
      t('admin.assignUserError'),
      () => {
        setUserDialogOpen(false);
      }
    );
  }, [assignTask?.postResponse]);

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.ADMIN_UNASSIGN_TASK,
      unassignTask?.postResponse,
      t('admin.unassignUserSuccess'),
      t('admin.unassignUserError'),
      () => {
        setUserDialogOpen(false);
      }
    );
  }, [unassignTask?.postResponse]);

  const handleAssignUser = (): void => {
    dispatch(
      postRequest(WeDataKey.ADMIN_ASSIGN_TASK, { task_id: props.taskId, user_id: selectedUserId })
    );
  };
  const handleUnassignUser = (): void => {
    dispatch(postRequest(WeDataKey.ADMIN_UNASSIGN_TASK, { task_id: props.taskId }));
  };

  const handleSkipTask = (): void => {};

  const handleTryAgain = (): void => {
    dispatch(postRequest(WeDataKey.ADMIN_EXECUTE_ERRONEOUS_TASK, { task_id: props.taskId }));
  };

  const getAssignedUserLabel = (): string | undefined => {
    if (props.data?.assigned_user?.id) {
      return `${props.data.assigned_user.full_name} (${props.data.assigned_user.email})`;
    }
  };

  const renderAssignUserDialog = (): React.ReactElement => {
    // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- logical OR between booleans
    const isLoading = assignTaskLoadState || unassignTaskLoadState;
    return (
      <WeAlertDialog
        title={t('admin.assignedUserDialogTitle')}
        isDialogOpen={userDialogOpen}
        isLoading={isLoading}
        setDialogOpen={setUserDialogOpen}
        buttons={
          <>
            <Button
              // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- logical OR between booleans
              disabled={isLoading || !props.data?.assigned_user}
              design={ButtonDesign.Negative}
              tooltip={t('admin.unassignUserTooltip')}
              onClick={() => {
                handleUnassignUser();
              }}>
              {t('admin.unassignUser')}
            </Button>
            <Button
              // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- logical OR between booleans
              disabled={isLoading || !selectedUserId}
              design={ButtonDesign.Emphasized}
              tooltip={t('admin.assignUserTooltip')}
              onClick={() => {
                handleAssignUser();
              }}>
              {t('admin.assignUser')}
            </Button>
          </>
        }>
        <WeUserAutocomplete
          initialLabel={getAssignedUserLabel()}
          onSelectUser={userId => {
            setSelectedUserId(userId);
          }}
        />
      </WeAlertDialog>
    );
  };

  // The workflow definition has been removed from all providers; admin actions on this task
  // cannot succeed (no script engine, no notifications), so disable them.
  const isReadonly = !!props.data?.is_readonly;

  return (
    <>
      <div className="flex gap-3">
        <Button
          icon="user-edit"
          design={ButtonDesign.Transparent}
          tooltip={t('admin.assignUserTooltip')}
          disabled={isReadonly}
          onClick={() => {
            setUserDialogOpen(true);
          }}
        />

        <BusyIndicator active={false} delay={0} size={BusyIndicatorSize.Small}>
          <Button
            icon="begin"
            design={ButtonDesign.Transparent}
            tooltip={t('admin.skipTasksTooltip')}
            disabled={isReadonly}
            onClick={() => {
              handleSkipTask();
            }}
          />
        </BusyIndicator>

        <BusyIndicator
          active={executeErroneousTaskLoadState}
          delay={0}
          size={BusyIndicatorSize.Small}>
          <Button
            icon="synchronize"
            design={ButtonDesign.Transparent}
            tooltip={t('admin.tryAgainTooltip')}
            disabled={!props.data?.state_error || isReadonly}
            onClick={() => {
              handleTryAgain();
            }}
          />
        </BusyIndicator>
      </div>
      {renderAssignUserDialog()}
    </>
  );
};
export default WeTaskHeaderActions;
