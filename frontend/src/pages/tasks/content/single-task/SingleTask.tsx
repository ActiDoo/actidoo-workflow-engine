// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { WeDataKey } from '@/store/generic-data/setup';
import { Text, BusyIndicator, Button, ButtonDesign, TextArea } from '@ui5/webcomponents-react';
import { getRequest, postRequest } from '@/store/generic-data/actions';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ErrorSchema,
  RJSFSchema,
  UiSchema,
} from '@rjsf/utils';
import _ from 'lodash';
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

// Import IndexedDB store service functions
import { openDB, getFormData, saveFormData, deleteFormData, deleteOldFormData } from '@/services/DBService';

// Import debounce from lodash to prevent excessive writes

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
  const [formRenderIndex, setFormRenderIndex] = useState(0);
  const [delegateDialogOpen, setDelegateDialogOpen] = useState(false);
  const [delegateComment, setDelegateComment] = useState('');
  const [pendingDelegateFormData, setPendingDelegateFormData] = useState<object | null>(null);
  const dbRef = useRef<IDBDatabase | null>(null); // Ref to hold the DB instance

  // Track whether the draft has been loaded from IndexedDB (prevents race condition)
  const [isDraftLoaded, setIsDraftLoaded] = useState(false);
  const isDraftLoadedRef = useRef(false);

  // Refs to hold the latest formData and task
  const formDataRef = useRef<object | undefined>(formData);
  const taskRef = useRef<typeof task>(task);

  // Update the refs whenever formData or task changes
  useEffect(() => {
    formDataRef.current = formData;
  }, [formData]);

  useEffect(() => {
    taskRef.current = task;
  }, [task]);

  // Update isDraftLoadedRef whenever isDraftLoaded changes
  useEffect(() => {
    isDraftLoadedRef.current = isDraftLoaded;
  }, [isDraftLoaded]);

  // Reset state when taskId changes (prevents stale data from previous task)
  useEffect(() => {
    setIsDraftLoaded(false);
    isDraftLoadedRef.current = false;
    setFormData(undefined);
    setErrorSchema(undefined);
  }, [taskId]);

  const submitRequest = useSelector((state: State) => state.data[WeDataKey.SUBMIT_TASK_DATA]);
  const loadingState = useSelector((state: State) => state.ui.loading);
  const isSubmitLoading = loadingState[`${WeDataKey.SUBMIT_TASK_DATA}POST`];
  const isLoading = isSubmitLoading;
  const isUploadLoadingDialogOpen = isSubmitLoading;

  const jsonschema: RJSFSchema | undefined = _.cloneDeep(task?.jsonschema);
  const uiSchema = (task?.uischema
    ? (_.cloneDeep(task.uischema) as UiSchema<any, RJSFSchema, any>)
    : undefined);
  const isBlockedByDelegateAssignment =
    !!(task?.assigned_to_me && task?.assigned_delegate_user && !task?.assigned_to_me_as_delegate);
  const canSubmitTask =
    !!(task?.assigned_to_me || task?.assigned_to_me_as_delegate) && !isBlockedByDelegateAssignment;
  const isDelegateSubmission = !!task?.assigned_to_me_as_delegate;

  if (jsonschema && uiSchema) {
    changeRequiredDefinitionForFieldsWithHideIfDefinition(jsonschema, uiSchema);
  }

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

          setTimeout(() => {
            if (savedFormData) {
              // Draft data found in IndexedDB - use it
              setFormData(savedFormData);
            } else if (taskRef.current?.data) {
              // No draft data, use server data as initial value
              setFormData(taskRef.current.data);
            }
          }, 100);
          // Note: if neither draft nor server data is available yet,
          // the separate useEffect for task?.data will handle it
        }
        // Mark draft as loaded - now saving is allowed
        setIsDraftLoaded(true);
        isDraftLoadedRef.current = true;
      } catch (error) {
        console.error('Failed to open IndexedDB:', error);
        if (isCancelled) return;
        // On error, fall back to server data and allow saving
        if (taskRef.current?.data) {
          setFormData(taskRef.current.data);
        }
        setIsDraftLoaded(true);
        isDraftLoadedRef.current = true;
      }
    };

    void initializeDB();

    // Cleanup function to close the DB when component unmounts or taskId changes
    return () => {
      isCancelled = true;
      if (dbRef.current) {
        dbRef.current.close();
        dbRef.current = null;
      }
    };
  }, [taskId]);

  // Load tasks if necessary
  useEffect(() => {
    if (!task || task.id !== taskId) loadTasks();
  }, [taskId]);

  // Update formData when task changes **only if draft is already loaded and formData is still undefined**
  // This handles the case where task.data arrives after IndexedDB check completed with no draft
  useEffect(() => {
    if (isDraftLoaded && task?.data && !formDataRef.current) {
      setFormData(task.data);
    }
  }, [task?.data, isDraftLoaded]);

  // Handle responses for submit
  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.SUBMIT_TASK_DATA,
      submitRequest?.postResponse,
      t('taskContent.submitSuccess'),
      t('taskContent.submitError'),
      () => {
        dispatch(
          postRequest(WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS, {}, { state: WorkflowState.READY })
        );
        navigate('/tasks/open');
        
        // Optionally, delete the draft from IndexedDB upon successful submit
        if (dbRef.current && task?.id) {
          deleteFormData(dbRef.current, task.id).catch(error => {
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

  const loadTasks = (): void => {
    if (workflowId)
      dispatch(
        getRequest(WeDataKey.MY_USER_TASKS, {
          queryParams: { workflow_instance_id: workflowId },
          params: { state: props.state },
        })
      );
  };

  const uploadProgress = (p: number): void => {
    setProgress(() => p);
  };

  const resetToInitialState = (): void => {
    if (formDataRef.current && taskRef.current?.id) {
      setResetToInitialStateDialogOpen(false);
      
      // Optionally, delete the draft from IndexedDB
      if (dbRef.current && taskRef.current.id) {
        deleteFormData(dbRef.current, taskRef.current.id).catch(error => {
          console.error('Failed to delete draft data:', error);
        });
      }
      
      if (task?.data) {
        setFormData(() => task.data);
      }
      setErrorSchema(undefined);
    }
  };


  // Define saveDraft without dependencies, using the refs
  const saveDraft = useCallback((): void => {
    const currentFormData = formDataRef.current;
    const currentTask = taskRef.current;

    if (currentFormData && currentTask?.id) {
      // Save to IndexedDB
      if (dbRef.current && currentTask.id) {
        saveFormData(dbRef.current, currentTask.id, currentFormData).catch(error => {
          console.error('Failed to save draft to IndexedDB:', error);
        });
      }
    }
  }, [dispatch]);

  // Debounced version of saveDraft to prevent excessive writes
  const debouncedSaveDraft = useRef(_.debounce(saveDraft, 100)).current;

  const submitData = (data: any, delegateCommentValue?: string): void => {
    if (data && task?.id) {
      const queryParams: StringDict = { task_id: task.id };
      if (delegateCommentValue && delegateCommentValue.trim().length > 0) {
        queryParams.delegate_comment = delegateCommentValue.trim();
      }
      dispatch(
        postRequest(
          WeDataKey.SUBMIT_TASK_DATA,
          data,
          undefined,
          queryParams,
          undefined,
          uploadProgress
        )
      );
    }
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
  const handleFormChange = (d: any) => {
    setFormData(prevData => {
      const updatedData = { ...prevData, ...d.formData };
      return updatedData;
    });
    // Only save to IndexedDB after draft has been loaded (prevents overwriting draft with server data)
    if (isDraftLoadedRef.current) {
      debouncedSaveDraft();
    }
  };

  if (loadingState[WeDataKey.MY_USER_TASKS] || !isDraftLoaded) {
    return (
      <div className="flex flex-col w-full h-full items-center justify-center pb-32 gap-2">
        <BusyIndicator active={true} delay={500} />
      </div>
    );
  }

  // console.log("** SingleTask *************************************************")
  // console.log(uiSchema)
  // console.log(jsonschema)

  if (task && jsonschema !== undefined && formData !== undefined) {
    // All relevant form information is stored inside these 3 objects.
    // This logging should clarify how FEEL functions are stored and where you have to adjust your code.
    // console.log("jsonschema", jsonschema)
    // console.log("formData", formData)
    return (
      <>
        <div className="pl-2">
          <SingleTaskHeader
            task={task}
            reloadTask={() => {
              loadTasks();
            }}
            backToList={() => {
              dispatch(
                postRequest(
                  WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS,
                  {},
                  { state: WorkflowState.READY }
                )
              );
              navigate('/tasks/open');
            }}
          />
          <div className="bg-white pt-4 px-12 pc-form pb-20">
            {/* This is the main part of the whole page. Will construct all input fields and other elements, based on the json scheme. */}
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
              progressLabel={
                isSubmitLoading ? t('taskContent.uploadForm') : t('taskContent.uploadDraft')
              }
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
