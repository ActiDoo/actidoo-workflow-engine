// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect } from 'react';
import { PcDetailsPage } from '@/ui5-components';
import { ObjectPageSection, Title, TitleLevel } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/synchronize';
import '@ui5/webcomponents-icons/dist/begin';
import '@ui5/webcomponents-icons/dist/cancel';
import '@ui5/webcomponents-icons/dist/user-edit';
import { Link, useParams } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { postRequest } from '@/store/generic-data/actions';
import WeEditableDataSection from '@/utils/components/WeEditableDataSection';
import WeTaskHeaderActions from '@/utils/components/tasks/WeTaskHeaderActions';
import WeTaskDetailsHeader from '@/utils/components/tasks/WeTaskDetailsHeader';
import { WeDetailsTable } from '@/utils/components/WeDetailsTable';
import { useTranslation } from '@/i18n';

const AdminTaskDetails: React.FC = () => {
  const { t } = useTranslation();
  const { taskId } = useParams();
  const dispatch = useDispatch();

  const data = useSelector(
    (state: State) => state.data[WeDataKey.ADMIN_ALL_TASKS]
  )?.data?.ITEMS.find(i => i.id === taskId);

  useEffect(() => {
    if (!data) dispatch(postRequest(WeDataKey.ADMIN_ALL_TASKS, {}, undefined, { f_id: taskId }));
  }, []);

  if (!taskId) return null;

  const headerActions = <WeTaskHeaderActions taskId={taskId} data={data} />;
  return (
    <PcDetailsPage
      header={{
        title: t('admin.taskDetailsTitle', { title: data?.title ?? '' }),
        actionSection: headerActions,
        showBack: true,
      }}
      headerContent={
        <>
          <div className=" flex gap-16 items-start pt-2 pb-6 border-t-1">
            {data ? (
              <WeTaskDetailsHeader
                task={data}
                additional={
                  <WeDetailsTable
                    data={[
                      {
                        label: t('admin.instanceId'),
                        content: data?.workflow_instance?.id ? (
                          <Link to={`/admin/all-workflows/${data.workflow_instance?.id}`}>
                            {data?.workflow_instance?.id}
                          </Link>
                        ) : null,
                      },
                      {
                        label: t('admin.instanceTitle'),
                        content: data?.workflow_instance?.title,
                      },
                    ]}
                  />
                }
              />
            ) : null}
          </div>
          {data?.error_stacktrace ? (
            <>
              <Title level={TitleLevel.H6}>{t('admin.errorMessage')}</Title>
              <div className="grid overflow-auto max-h-40 mb-4">
                <pre className="bg-neutral-50 p-2 rounded ">{data.error_stacktrace}</pre>
              </div>
            </>
          ) : null}
        </>
      }
      className={'!p-0'}>
      <ObjectPageSection
        className=" mt-8 "
        aria-label={t('admin.data')}
        id="data"
        titleText={t('admin.data')}>
        <Title level={TitleLevel.H4}>{t('admin.data')}</Title>
        <div className="bg-white p-4 rounded mt-2">
          <WeEditableDataSection taskId={taskId} data={data?.data} />
        </div>
      </ObjectPageSection>
      <ObjectPageSection
        className=" mt-8"
        aria-label={t('common.labels.workflowInstance')}
        id="workflowSchema"
        titleText={t('common.labels.workflowInstance')}>
        <div className="bg-white p-4 rounded mt-2 max-h-[500px] overflow-y-auto">
          <pre>{JSON.stringify(data?.workflow_instance, undefined, 2)}</pre>
        </div>
      </ObjectPageSection>
      <ObjectPageSection
        className=" mt-8"
        aria-label={t('common.labels.jsonSchema')}
        id="jsonSchema"
        titleText={t('common.labels.jsonSchema')}>
        <div className="bg-white p-4 rounded mt-2 max-h-[500px] overflow-y-auto">
          <pre>{JSON.stringify(data?.jsonschema, undefined, 2)}</pre>
        </div>
      </ObjectPageSection>
      <ObjectPageSection
        className=" mt-8"
        aria-label={t('common.labels.uiSchema')}
        id="uiSchema"
        titleText={t('common.labels.uiSchema')}>
        <div className="bg-white p-4 rounded mt-2 max-h-[500px] overflow-y-auto mb-8">
          <pre>{JSON.stringify(data?.uischema, undefined, 2)}</pre>
        </div>
      </ObjectPageSection>
    </PcDetailsPage>
  );
};
export default AdminTaskDetails;
