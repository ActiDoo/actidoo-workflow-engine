// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';
import '@/pages/admin/workflows/details/AdminWorkflowDetails.scss';
import { PcDynamicPage } from '@/ui5-components';
import { useParams, useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { WeDataKey } from '@/store/generic-data/setup';
import { postRequest } from '@/store/generic-data/actions';
import { Text, Button, ButtonDesign, DynamicPageHeader } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/activity-items.js';
import { useSelectCurrentAdminWorkflow } from '@/store/generic-data/selectors';
import AdminWorkflowDetailsHeader from '@/pages/admin/workflows/details/components/DetailsHeader';
import AdminWorkflowDetailsTasksSection from '@/pages/admin/workflows/details/components/TasksSection';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { handleResponse } from '@/services/HelperService';
import { State } from '@/store';
import WeAlertDialog from '@/utils/components/WeAlertDialog';
import { useTranslation } from '@/i18n';

const AdminWorkflowDetails: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { workflowId } = useParams();
  const navigate = useNavigate();

  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);

  const workflow = useSelectCurrentAdminWorkflow(workflowId);
  const cancelWorkflow = useSelector(
    (state: State) => state.data[WeDataKey.ADMIN_CANCEL_WORKFLOW_INSTANCE]
  );
  const cancelWorkflowLoadState = useSelectUiLoading(
    WeDataKey.ADMIN_CANCEL_WORKFLOW_INSTANCE,
    'POST'
  );

  useEffect(() => {
    if (!workflow) getWorkflow();
  }, []);

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.ADMIN_CANCEL_WORKFLOW_INSTANCE,
      cancelWorkflow?.postResponse,
      t('admin.cancelWorkflowSuccess'),
      t('admin.cancelWorkflowError'),
      () => {
        setCancelDialogOpen(false);
        navigate('/admin/all-workflows', { replace: true });
      }
    );
  }, [cancelWorkflow?.postResponse]);

  const handleCancelWorkflow = (): void => {
    dispatch(
      postRequest(WeDataKey.ADMIN_CANCEL_WORKFLOW_INSTANCE, { workflow_instance_id: workflowId })
    );
  };

  const getWorkflow = (): void => {
    dispatch(
      postRequest(WeDataKey.ADMIN_ALL_WORKFLOWS, {}, undefined, {
        f_id: workflowId,
      })
    );
  };

  const renderCancelWorkflowDialog = (): React.ReactElement => {
    const isLoading = cancelWorkflowLoadState;

    return (
      <WeAlertDialog
        isDialogOpen={cancelDialogOpen}
        setDialogOpen={setCancelDialogOpen}
        isLoading={isLoading}
        title={t('admin.cancelWorkflowTitle')}
        buttons={
          <>
            <Button
              disabled={isLoading}
              design={ButtonDesign.Transparent}
              tooltip={t('common.actions.abort')}
              onClick={() => {
                setCancelDialogOpen(false);
              }}>
              {t('common.actions.abort')}
            </Button>
            <Button
              disabled={isLoading}
              design={ButtonDesign.Negative}
              tooltip={t('admin.cancelWorkflowTitle')}
              onClick={() => {
                handleCancelWorkflow();
              }}>
              {t('admin.cancelWorkflowTitle')}
            </Button>
          </>
        }>
        <Text>{t('admin.cancelWorkflowConfirm')}</Text>
      </WeAlertDialog>
    );
  };

  return (
    <PcDynamicPage
      id="admin-workflow-details"
      header={{
        title: workflow?.title
          ? `${t('admin.workflowDetailsTitle')}: ${workflow.title}`
          : t('admin.workflowDetailsTitle'),
        showBack: true,
        actionSection: (
          <Button
            design={ButtonDesign.Negative}
            title={t('admin.cancelWorkflowTitle')}
            onClick={() => {
              setCancelDialogOpen(true);
            }}>
            {t('admin.cancelWorkflowTitle')}
          </Button>
        ),
      }}
      showHideHeaderButton={false}
      headerContentPinnable={false}
      headerContent={
        <DynamicPageHeader className="pc-px-responsive">
          <AdminWorkflowDetailsHeader workflow={workflow} />
        </DynamicPageHeader>
      }>
      <AdminWorkflowDetailsTasksSection />
      {renderCancelWorkflowDialog()}
    </PcDynamicPage>
  );
};

export default AdminWorkflowDetails;
