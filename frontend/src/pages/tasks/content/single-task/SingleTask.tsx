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
import {
  changeRequiredDefinitionForFieldsWithHideIfDefinition,
  computeHiddenMap,
} from '@/services/FeelService';
import { ROW_ID_KEY, FormTemplateMode, WorkflowState } from '@/models/models';
import { adoptServerRowIds, generateRowId, isDynamicListUiItems } from '@/utils/rowIdentity';
import { useSelectCurrentTask } from '@/store/generic-data/selectors';
import { useScrollTop } from '@/utils/hooks/useScrollTop';
import { WeUploadDialog } from '@/utils/components/WeUploadDialog';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { SingleTaskHeader } from '@/pages/tasks/content/single-task/SingleTaskHeader';
import { handleResponse } from '@/services/HelperService';
import { TaskActions } from '@/pages/tasks/content/TaskActions';
import FormTemplateActions from '@/pages/tasks/content/single-task/form-templates/FormTemplateActions';
import WeAlertDialog from '@/utils/components/WeAlertDialog';
import TaskForm from '@/rjsf-customs/components/TaskForm';
import {
  isAttachmentMultiSchema,
  isAttachmentSingleSchema,
  isRealFile,
} from '@/rjsf-customs/custom-fields/multiFileField/attachments';
import { useTranslation } from '@/i18n';
import { refreshWorkflowInstancesWithTasks } from '@/utils/hooks/useInfiniteWorkflowInstances';
import { StringDict } from '@/ui5-components';

import {
  openDB,
  getFormData,
  saveFormData,
  deleteFormData,
  deleteOldFormData,
  CURRENT_DRAFT_FORMAT,
  DRAFT_FORMAT_ROW_IDENTITY,
} from '@/services/DBService';

interface SingleTaskProps {
  state: WorkflowState;
}

/**
 * Brings freshly loaded form data (task data or a stored draft) into the shape the form
 * expects, before the form renders it. Historically the custom fields repaired the data
 * themselves while rendering, each with its own deferred onChange; under rjsf 6 these
 * corrections collide with re-renders and crash large forms. Normalizing once, up front,
 * keeps rendering free of data fixes.
 */
const prepareFormData = (
  jsonschema: any,
  uischema: any,
  data: Record<string, any>,
  serverData?: Record<string, any>
): { prepared: Record<string, any>; changed: boolean } => {
  const prepared = { ...data };
  let changed = false;
  const hiddenMap = computeHiddenMap(uischema ?? {}, jsonschema?.properties, data);
  for (const [key, prop] of Object.entries<any>(jsonschema?.properties ?? {})) {
    if (typeof prop !== 'object' || prop === null) continue;
    const ui = uischema?.[key] ?? {};
    const value = prepared[key];

    // Old drafts may still contain attachment placeholders like {}. Drop them, so a
    // required upload counts as missing rather than as an uploaded file.
    if (isAttachmentSingleSchema(prop)) {
      const isRequired = Array.isArray(jsonschema?.required) && jsonschema.required.includes(key);

      // Only values with attachment identifiers are real files. Everything else
      // (undefined, null, {}, or stale/corrupt data) means "no file selected".
      if (isRealFile(value)) continue;

      // Required single uploads must remain present as null; deleting the key lets
      // rjsf repopulate the required object as {}. Optional empty uploads can vanish.
      if (isRequired) {
        if (value !== null) {
          prepared[key] = null;
          changed = true;
        }
      } else if (value !== undefined) {
        delete prepared[key];
        changed = true;
      }
      continue;
    }

    if (isAttachmentMultiSchema(prop)) {
      const files = Array.isArray(value) ? value : [];
      const realFiles = files.filter(isRealFile);

      // Multi uploads are always arrays. RJSF may leave placeholder entries in
      // required arrays, so keep only real files and turn missing/stale values into [].
      if (files !== value || realFiles.length !== files.length) {
        prepared[key] = realFiles;
        changed = true;
      }
      continue;
    }

    // Itemgroup rows are nested forms — normalize each row the same way.
    const itemSchema =
      typeof prop.items === 'object' && !Array.isArray(prop.items) ? prop.items : undefined;
    if (prop.type === 'array' && itemSchema?.properties && Array.isArray(value)) {
      // Dynamic lists are recognized by their uischema signature; the technical
      // row id never appears in any schema, it lives in the form data only.
      const isDynamicList = isDynamicListUiItems(ui.items);
      const serverRows = Array.isArray(serverData?.[key]) ? serverData[key] : [];
      const seenRowIds = new Set<string>();
      let rowsChanged = false;
      const rows = value.map((row: any, index: number) => {
        // Invalid/stale rows should fail validation as-is; only real row objects
        // are nested forms that can be normalized recursively.
        if (row === null || typeof row !== 'object' || Array.isArray(row)) return row;
        let current = row;
        if (isDynamicList) {
          const rowId = current[ROW_ID_KEY];
          // Server rows arrive stamped, legacy drafts and templates get their ids
          // when they are loaded/applied - a row without an id here was just added
          // by the user. A duplicate means rjsf's copy-row button cloned a row
          // verbatim, and a copy IS a new row with its own identity, otherwise the
          // backend rejects the duplicate. Either way: mint. The backend cannot
          // take over here - a list whose rows all lack ids is indistinguishable
          // from one submitted by a client that never loaded the task, which the
          // submission validation rejects.
          if (typeof rowId !== 'string' || rowId === '' || seenRowIds.has(rowId)) {
            current = { ...current, [ROW_ID_KEY]: generateRowId() };
            rowsChanged = true;
          }
          seenRowIds.add(current[ROW_ID_KEY]);
        }
        const result = prepareFormData(itemSchema, ui.items ?? {}, current, serverRows[index]);
        rowsChanged = rowsChanged || result.changed;
        return result.changed ? result.prepared : current;
      });
      if (rowsChanged) {
        prepared[key] = rows;
        changed = true;
      }
      continue;
    }

    if (value !== undefined) continue;
    if (prop.default !== undefined) {
      prepared[key] = _.cloneDeep(prop.default);
      changed = true;
    } else if (prop.type === 'null') {
      prepared[key] = null;
      changed = true;
    } else if (prop.type === 'boolean' && ui['ui:widget'] !== 'hidden' && !hiddenMap[key]) {
      // Seed every currently-visible checkbox to false, so the submitted value equals the false
      // computeHiddenMap already assumed when rendering it. This keeps backend visibility aligned
      // with the frontend; a hidden checkbox stays absent (the backend then reads it as unset).
      prepared[key] = false;
      changed = true;
    }
  }
  return { prepared, changed };
};

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
  const [deleteDialogeOpen, setDeleteDialogeOpen] = useState(false);
  const [formRenderIndex, setFormRenderIndex] = useState(0);

  const [delegateDialogOpen, setDelegateDialogOpen] = useState(false);
  const [delegateComment, setDelegateComment] = useState('');
  const [pendingDelegateFormData, setPendingDelegateFormData] = useState<object | null>(null);

  const dbRef = useRef<IDBDatabase | null>(null);
  const submittedTaskIdRef = useRef<string | null>(null);

  const [isDraftLoaded, setIsDraftLoaded] = useState(false);
  // Format the loaded draft was stored in (see CURRENT_DRAFT_FORMAT); undefined
  // while no draft is loaded. Older formats are brought up to date by the
  // upgrade effect below once the task context is available.
  const [draftFormatVersion, setDraftFormatVersion] = useState<number | undefined>(undefined);

  const submitRequest = useSelector((state: State) => state.data[WeDataKey.SUBMIT_TASK_DATA]);
  const loadingState = useSelector((state: State) => state.ui.loading);
  const isSubmitLoading = loadingState[`${WeDataKey.SUBMIT_TASK_DATA}POST`];
  const isLoading = isSubmitLoading;
  const isUploadLoadingDialogOpen = isSubmitLoading;

  const handleDeleteWorkflow = (taskId: string): void => {
    dispatch(postRequest(WeDataKey.DELETE_WORKFLOW, { task_id: taskId }));
  };

  const jsonschema: RJSFSchema | undefined = _.cloneDeep(task?.jsonschema);
  const uiSchema = task?.uischema
    ? (_.cloneDeep(task.uischema) as UiSchema<any, RJSFSchema, any>)
    : undefined;

  // Form-level template mode lives in the uischema root (see form_transformation).
  const templateMode = (task?.uischema as { 'ui:templateMode'?: FormTemplateMode } | undefined)?.[
    'ui:templateMode'
  ];

  const isBlockedByDelegateAssignment = !!(
    task?.assigned_to_me &&
    task?.assigned_delegate_user &&
    !task?.assigned_to_me_as_delegate
  );
  const canSubmitTask =
    // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- logical OR: false should fall through
    !!(task?.assigned_to_me || task?.assigned_to_me_as_delegate) &&
    !isBlockedByDelegateAssignment &&
    !task?.is_readonly;
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
    setDraftFormatVersion(undefined);
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
          const savedDraft = await getFormData(db, taskId);
          if (isCancelled) return;

          // Only set draft here. Server fallback is handled in a separate effect after draft load is completed.
          if (savedDraft !== null) {
            setFormData(savedDraft.formData);
            setDraftFormatVersion(savedDraft.formatVersion ?? 0);
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

  // Bring a draft stored in an older format up to date, once draft and task are
  // both there. Steps run in version order and each compares against the format
  // that introduced it - a future format bump appends its step here.
  useEffect(() => {
    if (draftFormatVersion === undefined || draftFormatVersion >= CURRENT_DRAFT_FORMAT) return;
    if (!task || task.id !== taskId) return;
    if (formData === undefined) return;

    let data: unknown = formData;
    let changed = false;

    if (draftFormatVersion < DRAFT_FORMAT_ROW_IDENTITY) {
      // Rows of such a draft carry ids the server never issued. Map them onto the
      // stored rows - submitting them as-is would make the backend take every row
      // for a new one and drop the values it owns. Current-format drafts are never
      // touched: ids the server does not know are rows the user really added.
      const adopted = adoptServerRowIds(task.uischema, data, task.data);
      data = adopted.data;
      changed = changed || adopted.changed;
    }

    setDraftFormatVersion(CURRENT_DRAFT_FORMAT);
    if (changed) setFormData(data as object);
  }, [draftFormatVersion, task, taskId, formData]);

  // The form and everything that watches it (hide-if conditions, dynamic selects) must
  // all see the same, already-normalized data from the very first render on.
  const preparedFormData = useMemo(() => {
    if (!task?.jsonschema || task.id !== taskId || formData === undefined) return formData;
    return prepareFormData(task.jsonschema, task.uischema, formData, task.data ?? undefined)
      .prepared;
  }, [task, taskId, formData]);

  // Handle responses for submit
  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.SUBMIT_TASK_DATA,
      submitRequest?.postResponse,
      t('taskContent.submitSuccess'),
      t('taskContent.submitError'),
      () => {
        dispatch(refreshWorkflowInstancesWithTasks(WorkflowState.READY));
        // A task submit may have created/removed data-model rows (workflow-managed
        // models), which flips the "Daten" nav entry on/off — that catalog is
        // otherwise fetched only once on shell mount, so refresh it here.
        dispatch(getRequest(WeDataKey.WORKFLOW_DATA_MODELS));
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
  }, [submitRequest?.postResponse]); // eslint-disable-line

  const submitData = (data: any, delegateCommentValue?: string): void => {
    if (!data || !taskId) return;

    submittedTaskIdRef.current = taskId;

    const queryParams: StringDict = { task_id: taskId };
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
                setDelegateComment(event.currentTarget?.value ?? '');
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
    // The form now shows server data, not a stored draft - nothing left to upgrade.
    setDraftFormatVersion(undefined);
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
              className="transparent-button-gray"
              design={ButtonDesign.Transparent}
              tooltip={t('common.actions.cancel')}
              onClick={() => {
                setResetToInitialStateDialogOpen(false);
              }}>
              {t('common.actions.cancel')}
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
  const renderDeleteStateDialog = (): React.ReactElement => {
    if (!task) return <></>;
    return (
      <WeAlertDialog
        isDialogOpen={deleteDialogeOpen}
        setDialogOpen={setDeleteDialogeOpen}
        isLoading={false}
        title={t('taskContent.deleteDialogTitle')}
        buttons={
          <>
            <Button
              disabled={false}
              design={ButtonDesign.Transparent}
              tooltip={t('common.actions.abort')}
              onClick={() => {
                setDeleteDialogeOpen(false);
              }}>
              {t('common.actions.abort')}
            </Button>
            <Button
              disabled={false}
              design={ButtonDesign.Negative}
              tooltip={t('common.actions.delete')}
              onClick={() => {
                handleDeleteWorkflow(task?.id);
                setDeleteDialogeOpen(false);
              }}>
              {t('common.actions.delete')}
            </Button>
          </>
        }>
        <Text>{t('taskContent.deleteDialogText')}</Text>
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
        void debouncedSaveDraft(taskId, next);
      }
    },
    [isDraftLoaded, taskId, debouncedSaveDraft]
  );

  // Apply a template: replace the controlled formData and remount RJSF so it picks up the new values.
  const handleApplyTemplate = useCallback(
    (data: object) => {
      // Templates never store the technical row id, so their list rows arrive
      // without identity. Re-link them to the rows currently in the form by
      // position - the template changes values, not which rows exist. Rows
      // beyond the current ones are genuinely new and get a fresh id later.
      const current = formData ?? task?.data ?? {};
      const next = adoptServerRowIds(task?.uischema, _.cloneDeep(data), current).data as object;
      setFormData(next);
      setFormRenderIndex(index => index + 1);
      if (isDraftLoaded && taskId) {
        void debouncedSaveDraft(taskId, next);
      }
    },
    [isDraftLoaded, taskId, debouncedSaveDraft, formData, task]
  );

  if (loadingState[WeDataKey.MY_USER_TASKS] || !isDraftLoaded || (task && formData === undefined)) {
    return (
      <div className="flex flex-col w-full h-full items-center justify-center pb-32 gap-2">
        <BusyIndicator active={true} delay={500} />
      </div>
    );
  }

  if (task && jsonschema !== undefined && formData !== undefined) {
    return (
      <>
        <div className="md:pl-2">
          <SingleTaskHeader
            task={task}
            reloadTask={() => {
              loadTasks();
            }}
            backToList={() => {
              dispatch(refreshWorkflowInstancesWithTasks(WorkflowState.READY));
              navigate('/tasks/open');
            }}
          />
          <div className="bg-white pt-4 px-3 md:px-12 pc-form pb-20">
            {taskId &&
            canSubmitTask &&
            props.state !== WorkflowState.COMPLETED &&
            templateMode &&
            templateMode !== 'off' ? (
              <FormTemplateActions
                taskId={taskId}
                jsonschema={jsonschema}
                formData={formData}
                onApply={handleApplyTemplate}
              />
            ) : null}
            <TaskForm
              key={`form_${formRenderIndex}`}
              id="single-task-form"
              formData={preparedFormData}
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
                formData: preparedFormData,
                schema: task.jsonschema,
                uiSchema: task.uischema,
              }}></TaskForm>

            <WeUploadDialog
              isOpen={isUploadLoadingDialogOpen}
              progress={progress}
              progressLabel={
                isSubmitLoading ? t('taskContent.uploadForm') : t('taskContent.uploadDraft')
              }
              processLabel={
                isSubmitLoading ? t('taskContent.processForm') : t('taskContent.processDraft')
              }
            />
          </div>
          <div className="sticky bottom-0 bg-white/85 px-3 pb-2.5 pt-2">
            <div className="mb-3 h-px w-full bg-gray-200" />
            {canSubmitTask && props.state !== WorkflowState.COMPLETED ? (
              <TaskActions
                task={task}
                disabled={isLoading}
                onReset={() => {
                  setResetToInitialStateDialogOpen(true);
                }}
                onDelete={() => {
                  setDeleteDialogeOpen(true);
                }}
              />
            ) : (
              <div></div>
            )}
          </div>
        </div>

        {renderDelegateConfirmationDialog()}
        {renderResetToInitialStateDialog()}
        {renderDeleteStateDialog()}
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
