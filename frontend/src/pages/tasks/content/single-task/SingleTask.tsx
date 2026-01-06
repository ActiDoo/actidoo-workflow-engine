// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { WeDataKey } from '@/store/generic-data/setup';
import { Text, BusyIndicator, Button, ButtonDesign } from '@ui5/webcomponents-react';
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
  const [formData, setFormData] = useState<object | undefined>(task?.data);
  const [errorSchema, setErrorSchema] = useState<ErrorSchema | undefined>(undefined);
  const [resetToInitialStateDialogOpen, setResetToInitialStateDialogOpen] = useState(false);
  const [formRenderIndex, setFormRenderIndex] = useState(0);
  const dbRef = useRef<IDBDatabase | null>(null); // Ref to hold the DB instance

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

  const submitRequest = useSelector((state: State) => state.data[WeDataKey.SUBMIT_TASK_DATA]);
  const loadingState = useSelector((state: State) => state.ui.loading);
  const isSubmitLoading = loadingState[`${WeDataKey.SUBMIT_TASK_DATA}POST`];
  const isLoading = isSubmitLoading;
  const isUploadLoadingDialogOpen = isSubmitLoading;

  const jsonschema: RJSFSchema | undefined = _.cloneDeep(task?.jsonschema);
  const uiSchema = (task?.uischema
    ? (_.cloneDeep(task.uischema) as UiSchema<any, RJSFSchema, any>)
    : undefined);

  if (jsonschema && uiSchema) {
    changeRequiredDefinitionForFieldsWithHideIfDefinition(jsonschema, uiSchema);
  }

  // Initialize IndexedDB and load draft data
  useEffect(() => {
    const initializeDB = async () => {
      try {
        const db = await openDB();
        dbRef.current = db;

        await deleteOldFormData(db)

        if (taskId) {
          const savedFormData = await getFormData(db, taskId);
          if (savedFormData) {
            setFormData(savedFormData);
          }
        }
      } catch (error) {
        console.error('Failed to open IndexedDB:', error);
      }
    };

    void initializeDB();

    // Cleanup function to close the DB when component unmounts
    return () => {
      if (dbRef.current) {
        dbRef.current.close();
      }
    };
  }, [taskId]);

  // Load tasks if necessary
  useEffect(() => {
    if (!task || task.id !== taskId) loadTasks();
  }, [taskId]);

  // Update formData when task changes **only if no draft is present**
  useEffect(() => {
    const updateFormData = async () => {
      if (task?.data && !formDataRef.current) {
        setFormData(() => task.data);
      }
    };
    void updateFormData();
  }, [task]);

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

  const submitData = (data: any): void => {
    if (data && task?.id) {
      // Dispatch Redux action
      dispatch(
        postRequest(
          WeDataKey.SUBMIT_TASK_DATA,
          data,
          undefined,
          { task_id: task.id },
          undefined,
          uploadProgress
        )
      );
    }
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
    // Save draft to IndexedDB (debounced)
    debouncedSaveDraft();
  };

  if (loadingState[WeDataKey.MY_USER_TASKS]) {
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
              className={`max-w-7xl ${!task.assigned_user || isLoading ? 'opacity-30' : ''}`}
              disabled={
                !task.assigned_to_me || isLoading || props.state === WorkflowState.COMPLETED
              }
              schema={jsonschema}
              uiSchema={uiSchema}
              extraErrors={errorSchema}
              showErrorList={false}
              onChange={handleFormChange}
              onSubmit={data => {
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
              {task.assigned_to_me && props.state !== WorkflowState.COMPLETED ? (
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
