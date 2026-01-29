// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useParams } from 'react-router-dom';
import _ from 'lodash';
import { BusyIndicator, Button, ButtonDesign, Text, TextArea } from '@ui5/webcomponents-react';
import { ErrorSchema, RJSFSchema, UiSchema } from '@rjsf/utils';

import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest } from '@/store/generic-data/actions';
import { State } from '@/store';
import { changeRequiredDefinitionForFieldsWithHideIfDefinition } from '@/services/FeelService';
import { useSelectCurrentTask } from '@/store/generic-data/selectors';
import { useScrollTop } from '@/utils/hooks/useScrollTop';
import { WeUploadDialog } from '@/utils/components/WeUploadDialog';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { SingleTaskHeader } from '@/pages/tasks/content/single-task/SingleTaskHeader';
import { WorkflowState } from '@/models/models';
import { handleResponse } from '@/services/HelperService';
import { TaskActions } from '@/pages/tasks/content/TaskActions';
import WeAlertDialog from '@/utils/components/WeAlertDialog';
import TaskForm from '@/rjsf-customs/components/TaskForm';
import { useTranslation } from '@/i18n';
import { StringDict } from '@/ui5-components';

import { openDB, getFormData, saveFormData, deleteFormData, deleteOldFormData } from '@/services/DBService';

interface SingleTaskProps {
  state: WorkflowState;
}

const SingleTask: React.FC<SingleTaskProps> = props => {
  const { t } = useTranslation();
  const { workflowId, taskId } = useParams<{ workflowId: string; taskId: string }>();
  const navigate = useNavigate();
  const dispatch = useDispatch();

  const task = useSelectCurrentTask(taskId);
  const [scrollToTop] = useScrollTop();

  const [progress, setProgress] = useState(0);
  const [formData, setFormData] = useState<object | undefined>(undefined);
  const [errorSchema, setErrorSchema] = useState<ErrorSchema | undefined>(undefined);

  const [resetToInitialStateDialogOpen, setResetToInitialStateDialogOpen] = useState(false);
  const [formRenderIndex] = useState(0);

  const [delegateDialogOpen, setDelegateDialogOpen] = useState(false);
  const [delegateComment, setDelegateComment] = useState('');
  const [pendingDelegateFormData, setPendingDelegateFormData] = useState<object | null>(null);

  const dbRef = useRef<IDBDatabase | null>(null);
  const submittedTaskIdRef = useRef<string | null>(null);

  const [isDraftLoaded, setIsDraftLoaded] = useState(false);

  const submitRequest = useSelector((state: State) => state.data[WeDataKey.SUBMIT_TASK_DATA]);
  const loadingState = useSelector((state: State) => state.ui.loading);
  const isSubmitLoading = loadingState[`${WeDataKey.SUBMIT_TASK_DATA}POST`];
  const isLoading = isSubmitLoading;
  const isUploadLoadingDialogOpen = isSubmitLoading;

  const jsonschema: RJSFSchema | undefined = _.cloneDeep(task?.jsonschema);
  const uiSchema = task?.uischema ? (_.cloneDeep(task.uischema) as UiSchema<any, RJSFSchema, any>) : undefined;

  const isBlockedByDelegateAssignment =
    !!(task?.assigned_to_me && task?.assigned_delegate_user && !task?.assigned_to_me_as_delegate);
  const canSubmitTask =
    !!(task?.assigned_to_me || task?.assigned_to_me_as_delegate) && !isBlockedByDelegateAssignment;
  const isDelegateSubmission = !!task?.assigned_to_me_as_delegate;

  if (jsonschema && uiSchema) {
    changeRequiredDefinitionForFieldsWithHideIfDefinition(jsonschema, uiSchema);
  }

  const uploadProgress = (p: number): void => {
    setProgress(() => p);
  };

  const loadTasks = useCallback((): void => {
    if (!workflowId) return;

    dispatch(
      getRequest(WeDataKey.MY_USER_TASKS, {
        queryParams: { workflow_instance_id: workflowId },
        params: { state: props.state },
      })
    );
  }, [dispatch, workflowId, props.state]);

  // Reset state when taskId changes (prevents stale data from previous task)
  useEffect(() => {
    setIsDraftLoaded(false);
    setFormData(undefined);
    setErrorSchema(undefined);
  }, [taskId]);

  // Debounced draft saver: always saves the data for the taskId provided at call-time (prevents ref races)
  const debouncedSaveDraft = useMemo(
    () =>
      _.debounce(async (id: string, data: object) => {
        const db = dbRef.current;
        if (!db) return;

        try {
          await saveFormData(db, id, data);
        } catch (error) {
          console.error('Failed to save draft to IndexedDB:', error);
        }
      }, 250),
    []
  );

  // Cancel pending debounced saves on unmount
  useEffect(() => {
    return () => {
      debouncedSaveDraft.cancel();
    };
  }, [debouncedSaveDraft]);

  // Cancel pending saves when taskId changes (prevents a prior task save from firing after reset/delete)
  useEffect(() => {
    debouncedSaveDraft.cancel();
  }, [taskId, debouncedSaveDraft]);

  // Initialize IndexedDB and load draft data (runs only when taskId changes)
  useEffect(() => {
    let isCancelled = false;

    const initializeDB = async () => {
      try {
        const db = await openDB();
        if (isCancelled) return;

        dbRef.current = db;

        await deleteOldFormData(db);

        if (taskId) {
          const savedFormData = await getFormData(db, taskId);
          if (isCancelled) return;

          // Only set draft here. Server fallback is handled in a separate effect after draft load is completed.
          if (savedFormData !== undefined && savedFormData !== null) {
            setFormData(savedFormData);
          }
        }

        setIsDraftLoaded(true);
      } catch (error) {
        console.error('Failed to open IndexedDB:', error);
        if (isCancelled) return;

        // Even on error, allow rendering and server fallback.
        setIsDraftLoaded(true);
      }
    };

    void initializeDB();

    return () => {
      isCancelled = true;
      debouncedSaveDraft.cancel();

      if (dbRef.current) {
        dbRef.current.close();
        dbRef.current = null;
      }
    };
  }, [taskId, debouncedSaveDraft]);

  // Load tasks if necessary
  useEffect(() => {
    if (!taskId) return;
    if (!task || task.id !== taskId) loadTasks();
  }, [taskId, task?.id, task, loadTasks]);

  // Server fallback after draft-check is completed, only for the current taskId, and only if formData is still undefined.
  useEffect(() => {
    if (!isDraftLoaded) return;
    if (!taskId) return;
    if (!task || task.id !== taskId) return;
    if (formData !== undefined) return;

    setFormData(task.data ?? {});
  }, [isDraftLoaded, task, taskId, formData]);

  // Handle responses for submit
  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.SUBMIT_TASK_DATA,
      submitRequest?.postResponse,
      t('taskContent.submitSuccess'),
      t('taskContent.submitError'),
      () => {
        dispatch(postRequest(WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS, {}, { state: WorkflowState.READY }));
        navigate('/tasks/open');

        // Delete the draft for the task that was actually submitted (prevents deleting the wrong one on fast navigation)
        const submittedId = submittedTaskIdRef.current;
        submittedTaskIdRef.current = null;

        if (dbRef.current && submittedId) {
          debouncedSaveDraft.cancel();
          deleteFormData(dbRef.current, submittedId).catch(error => {
            console.error('Failed to delete draft data:', error);
          });
        }
      },
      () => {
        if (submitRequest?.data && 'error_schema' in submitRequest.data) {
          setErrorSchema(submitRequest.data.error_schema);
        } else {
          setErrorSchema(undefined);
        }
      }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submitRequest?.postResponse]);

  const submitData = (data: any, delegateCommentValue?: string): void => {
    if (!data || !taskId) return;

    submittedTaskIdRef.current = taskId;

    const queryParams: StringDict = { task_id: taskId };
    if (delegateCommentValue && delegateCommentValue.trim().length > 0) {
      queryParams.delegate_comment = delegateCommentValue.trim();
    }

    dispatch(
      postRequest(WeDataKey.SUBMIT_TASK_DATA, data, undefined, queryParams, undefined, uploadProgress)
    );
  };

  const closeDelegateDialog = (): void => {
    setDelegateDialogOpen(false);
    setDelegateComment('');
    setPendingDelegateFormData(null);
  };

  const handleDelegateConfirm = (): void => {
    if (pendingDelegateFormData) {
      submitData(pendingDelegateFormData, delegateComment);
      closeDelegateDialog();
    }
  };

  const renderDelegateConfirmationDialog = (): React.ReactElement => {
    if (!task) return <></>;

    return (
      <WeAlertDialog
        title="Confirm delegated submission"
        isDialogOpen={delegateDialogOpen}
        isLoading={isSubmitLoading}
        setDialogOpen={isOpen => {
          if (!isOpen) {
            closeDelegateDialog();
          } else {
            setDelegateDialogOpen(true);
          }
        }}
        buttons={
          <>
            <Button
              design={ButtonDesign.Transparent}
              onClick={() => {
                closeDelegateDialog();
              }}>
              Cancel
            </Button>
            <Button
              design={ButtonDesign.Emphasized}
              disabled={!pendingDelegateFormData || isSubmitLoading}
              onClick={() => {
                handleDelegateConfirm();
              }}>
              Confirm & Submit
            </Button>
          </>
        }>
        <div className="flex flex-col gap-2">
          <Text>
            You are acting as a delegate for{' '}
            <span className="font-semibold">{task.assigned_user?.full_name ?? 'this user'}</span>.
            Please confirm that you are authorized to submit this task on their behalf.
          </Text>
          <div className="flex flex-col gap-1">
            <Text className="text-sm text-neutral-700">Comment for the task owner (optional)</Text>
            <TextArea
              value={delegateComment}
              rows={3}
              placeholder="Add an optional comment"
              onInput={event => {
                setDelegateComment(event.currentTarget.value);
              }}
            />
          </div>
        </div>
      </WeAlertDialog>
    );
  };

  const resetToInitialState = (): void => {
    if (!taskId || !task) return;

    setResetToInitialStateDialogOpen(false);

    // Prevent pending debounced writes from re-creating the draft after deletion
    debouncedSaveDraft.cancel();

    if (dbRef.current) {
      deleteFormData(dbRef.current, taskId).catch(error => {
        console.error('Failed to delete draft data:', error);
      });
    }

    setFormData(task.data ?? {});
    setErrorSchema(undefined);
  };

  const renderResetToInitialStateDialog = (): React.ReactElement => {
    return (
      <WeAlertDialog
        isDialogOpen={resetToInitialStateDialogOpen}
        setDialogOpen={setResetToInitialStateDialogOpen}
        isLoading={false}
        title={t('taskContent.resetDialogTitle')}
        buttons={
          <>
            <Button
              disabled={false}
              design={ButtonDesign.Transparent}
              tooltip={t('common.actions.abort')}
              onClick={() => {
                setResetToInitialStateDialogOpen(false);
              }}>
              {t('common.actions.abort')}
            </Button>
            <Button
              disabled={false}
              design={ButtonDesign.Negative}
              tooltip={t('common.actions.reset')}
              onClick={() => {
                resetToInitialState();
              }}>
              {t('common.actions.reset')}
            </Button>
          </>
        }>
        <Text>{t('taskContent.resetDialogText')}</Text>
      </WeAlertDialog>
    );
  };

  // Handle form changes and save draft
  const handleFormChange = useCallback(
    (d: any) => {
      // RJSF typically provides the full formData object; do not shallow-merge.
      const next = _.cloneDeep(d.formData ?? {});
      setFormData(next);

      // Save only after draft check completed (prevents overwriting an existing draft during initialization)
      if (isDraftLoaded && taskId) {
        debouncedSaveDraft(taskId, next);
      }
    },
    [isDraftLoaded, taskId, debouncedSaveDraft]
  );

  if (
    loadingState[WeDataKey.MY_USER_TASKS] ||
    !isDraftLoaded ||
    (task && formData === undefined)
  ) {
    return (
      <div className="flex flex-col w-full h-full items-center justify-center pb-32 gap-2">
        <BusyIndicator active={true} delay={500} />
      </div>
    );
  }

  if (task && jsonschema !== undefined && formData !== undefined) {
    return (
      <>
        <div className="pl-2">
          <SingleTaskHeader
            task={task}
            reloadTask={() => {
              loadTasks();
            }}
            backToList={() => {
              dispatch(postRequest(WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS, {}, { state: WorkflowState.READY }));
              navigate('/tasks/open');
            }}
          />
          <div className="bg-white pt-4 px-12 pc-form pb-20">
            <TaskForm
              key={`form_${formRenderIndex}`}
              formData={formData}
              className={`max-w-7xl ${!canSubmitTask || isLoading ? 'opacity-30' : ''}`}
              disabled={!canSubmitTask || isLoading || props.state === WorkflowState.COMPLETED}
              schema={jsonschema}
              uiSchema={uiSchema}
              extraErrors={errorSchema}
              showErrorList={false}
              onChange={handleFormChange}
              onSubmit={data => {
                if (isDelegateSubmission) {
                  setPendingDelegateFormData(data.formData);
                  setDelegateDialogOpen(true);
                  return;
                }
                submitData(data.formData);
              }}
              onError={() => {
                scrollToTop();
              }}
              noHtml5Validate={false}
              formContext={{
                formData,
                schema: task.jsonschema,
                uiSchema: task.uischema,
              }}>
              {canSubmitTask && props.state !== WorkflowState.COMPLETED ? (
                <TaskActions
                  disabled={isLoading}
                  onReset={() => {
                    setResetToInitialStateDialogOpen(true);
                  }}
                />
              ) : (
                <div></div>
              )}
            </TaskForm>

            <WeUploadDialog
              isOpen={isUploadLoadingDialogOpen}
              progress={progress}
              progressLabel={isSubmitLoading ? t('taskContent.uploadForm') : t('taskContent.uploadDraft')}
              processLabel={isSubmitLoading ? t('taskContent.processForm') : t('taskContent.processDraft')}
            />
          </div>
        </div>

        {renderDelegateConfirmationDialog()}
        {renderResetToInitialStateDialog()}
      </>
    );
  }

  return (
    <WeEmptySection
      icon="search"
      title={t('taskContent.notFoundTitle')}
      text={t('taskContent.notFoundText')}
    />
  );
};

export default SingleTask;
