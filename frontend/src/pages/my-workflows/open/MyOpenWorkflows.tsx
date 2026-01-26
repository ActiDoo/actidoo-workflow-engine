// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useMemo, useState } from 'react';

import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { getRequest, postRequest } from '@/store/generic-data/actions';
import {
  calculateInitialPage,
  getQueryParamsFromTableData,
  getTableDataFromQueryParams,
  PcAnalyticalTable,
  StringDict,
  useAdditionalTableFunctions,
  PcSearch,
} from '@/ui5-components';
import { environment } from '@/environment';
import { ActiveTaskInstance, WorkflowState } from '@/models/models';
import { myOpenWorkflowsColumns } from '@/pages/my-workflows/open/MyOpenWorkflowsSettings';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { WeTaskSubRow } from '@/utils/components/WeTaskSubRow';
import { useTranslation } from '@/i18n';
import { WeCompletedTaskSubRow } from '@/utils/components/WeCompletedTaskSubRow';
import { useSelectCurrentTask } from '@/store/generic-data/selectors';
import { changeRequiredDefinitionForFieldsWithHideIfDefinition } from '@/services/FeelService';
import {
  BusyIndicator,
  BusyIndicatorSize,
  Button,
  Dialog,
  Icon,
  Text,
  Title,
  TitleLevel,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/decline';
import { createPortal } from 'react-dom';
import { RJSFSchema, UiSchema } from '@rjsf/utils';
import _ from 'lodash';
import TaskForm from '@/rjsf-customs/components/TaskForm';

const MyOpenWorkflows: React.FC = () => {
  const { t } = useTranslation();
  const key = WeDataKey.MY_OPEN_WORKFLOW_INSTANCES;
  const dispatch = useDispatch();
  const [submittedFormDialogOpen, setSubmittedFormDialogOpen] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const data = useSelector((state: State) => state.data[key]);
  const user = useSelector((state: State) => state.data[WeDataKey.WFE_USER])?.data;
  const loadingState = useSelectUiLoading(key, 'POST');
  const submittedFormLoading = useSelectUiLoading(WeDataKey.MY_USER_TASKS);
  const submittedTask = useSelectCurrentTask(selectedTaskId ?? undefined);
  const [offset, search, filter, sort] = getTableDataFromQueryParams(data?.queryParams);
  const finalFilter: StringDict = { ...filter, is_completed: false };
  const [tableData] = useAdditionalTableFunctions(
    environment.tableCount,
    offset,
    search,
    finalFilter,
    sort
  );

  useEffect(() => {
    dispatch(
      postRequest(key, {}, undefined, {
        ...getQueryParamsFromTableData(tableData, environment.tableCount),
        keepData: true,
      })
    );
  }, [tableData.loadData]);

  const openSubmittedForm = (workflowId: string, taskId?: string): void => {
    if (!taskId) return;
    setSelectedTaskId(taskId);
    setSubmittedFormDialogOpen(true);
    dispatch(
      getRequest(WeDataKey.MY_USER_TASKS, {
        queryParams: { workflow_instance_id: workflowId },
        params: { state: WorkflowState.COMPLETED },
      })
    );
  };

  const closeSubmittedForm = (): void => {
    setSubmittedFormDialogOpen(false);
    setSelectedTaskId(null);
  };

  const submittedFormSchema = useMemo(() => {
    if (!submittedTask?.jsonschema) return null;
    const schema = _.cloneDeep(submittedTask.jsonschema) as RJSFSchema;
    const uiSchema = submittedTask.uischema
      ? (_.cloneDeep(submittedTask.uischema) as UiSchema)
      : undefined;
    if (uiSchema) {
      changeRequiredDefinitionForFieldsWithHideIfDefinition(schema, uiSchema);
    }
    return { schema, uiSchema };
  }, [submittedTask]);

  const renderRowSubComponent = (row: any): React.ReactElement | null => {
    const activeTasks: ActiveTaskInstance[] | undefined = row.values.active_tasks;
    const completedTasks: ActiveTaskInstance[] = (row.original.completed_tasks ?? []).filter(
      (task: ActiveTaskInstance) =>
        task.completed_by_user?.id === user?.id ||
        task.completed_by_delegate_user?.id === user?.id
    );
    if ((activeTasks && activeTasks.length > 1) || completedTasks.length > 0) {
      return (
        <div className="space-y-4">
          {activeTasks && activeTasks.length > 1 ? (
            <WeTaskSubRow
              title={t('myWorkflows.activeTasksOfWorkflow')}
              tasks={activeTasks}
              userId={user?.id}
              workflowId={row.original.id}
            />
          ) : null}
          {completedTasks.length > 0 ? (
            <WeCompletedTaskSubRow
              title={t('myWorkflows.completedTasksOfWorkflow')}
              tasks={completedTasks}
              onShowForm={(taskId: string) => {
                openSubmittedForm(row.original.id, taskId);
              }}
            />
          ) : null}
        </div>
      );
    }
    return null;
  };

  const dialogTitle = submittedTask?.title
    ? t('myWorkflows.submittedFormTitleWithTask', { title: submittedTask.title })
    : t('myWorkflows.submittedFormTitle');

  const submittedFormContent =
    submittedFormSchema && submittedTask?.data ? (
      <div className="bg-white pt-2 px-6 pc-form pb-6">
        <TaskForm
          formData={submittedTask.data}
          className="max-w-7xl"
          disabled={true}
          schema={submittedFormSchema.schema}
          uiSchema={submittedFormSchema.uiSchema}
          showErrorList={false}
          formContext={{
            formData: submittedTask.data,
            schema: submittedTask.jsonschema,
            uiSchema: submittedTask.uischema,
            taskId: submittedTask.id,
          }}
        />
      </div>
    ) : (
      <Text>{t('myWorkflows.submittedFormUnavailable')}</Text>
    );

  return (
    <>
      <div className="flex items-center justify-end w-100 mb-4 gap-2 -mt-4">
        <PcSearch initialSearch={search} searchInput={tableData.onSearch} />
      </div>
      <div className="my-workflows-table">
        <PcAnalyticalTable
          columns={myOpenWorkflowsColumns(tableData, user?.id, t, openSubmittedForm)}
          initialPage={calculateInitialPage(tableData.offset, environment.tableCount)}
          data={data?.data?.ITEMS ?? []}
          loading={loadingState}
          response={data?.response}
          pageChange={tableData.onPageClick}
          filter={tableData.filter}
          sort={tableData.sort}
          onSort={tableData.onSort}
          itemsCount={data?.data?.COUNT}
          limit={environment.tableCount}
          forcePage={tableData.forcePage}
          filterable={true}
          renderRowSubComponent={renderRowSubComponent}
        />
      </div>
      {createPortal(
        <Dialog
          open={submittedFormDialogOpen}
          header={
            <div className="w-full flex items-center gap-2">
              <Title level={TitleLevel.H5} className="w-full py-2">
                {dialogTitle}
              </Title>
              <Icon className="cursor-pointer" name="decline" onClick={closeSubmittedForm} />
            </div>
          }
          footer={
            <div className="w-full flex justify-end mt-2">
              <Button onClick={closeSubmittedForm}>{t('common.actions.close')}</Button>
            </div>
          }
          style={{ width: 'min(92vw, 1200px)' }}>
          <BusyIndicator
            active={submittedFormLoading}
            delay={0}
            size={BusyIndicatorSize.Medium}
            className="bg-white/80 w-full">
            <div className="w-full flex flex-column">
              {submittedFormDialogOpen ? submittedFormContent : null}
            </div>
          </BusyIndicator>
        </Dialog>,
        document.body
      )}
    </>
  );
};

export default MyOpenWorkflows;
