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

  // A finished instance has nothing left to cancel - the backend refuses it with 409.
  const canCancelWorkflow = workflow !== undefined && !workflow.is_completed;

  useEffect(() => {
    if (!workflow) getWorkflow();
  }, []);

  // A 409 carries a `code` that says why the workflow was not cancelled; the
  // store keeps the error body in `data`.
  const cancelErrorText = (): string => {
    const errorBody = cancelWorkflow?.data as { code?: string } | undefined;
    if (errorBody?.code === 'workflow_instance_already_finished') {
      return t('admin.cancelWorkflowAlreadyFinished');
    }
    return t('admin.cancelWorkflowError');
  };

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.ADMIN_CANCEL_WORKFLOW_INSTANCE,
      cancelWorkflow?.postResponse,
      t('admin.cancelWorkflowSuccess'),
      cancelErrorText(),
      () => {
        setCancelDialogOpen(false);
        navigate('/admin/all-workflows', { replace: true });
      },
      () => {
        // The instance may have finished while this page was open - reload so the
        // header and the cancel button match the server again.
        setCancelDialogOpen(false);
        getWorkflow();
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
              className="transparent-button-gray"
              design={ButtonDesign.Transparent}
              tooltip={t('admin.keepWorkflowTitle')}
              onClick={() => {
                setCancelDialogOpen(false);
              }}>
              {t('admin.keepWorkflowTitle')}
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
        actionSection: canCancelWorkflow ? (
          <Button
            design={ButtonDesign.Negative}
            title={t('admin.cancelWorkflowTitle')}
            onClick={() => {
              setCancelDialogOpen(true);
            }}>
            {t('admin.cancelWorkflowTitle')}
          </Button>
        ) : undefined,
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
