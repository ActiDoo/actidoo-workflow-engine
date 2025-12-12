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

const AdminWorkflowDetails: React.FC = () => {
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
      'Workflow successfully canceld',
      'Task could not be executed. Please try again.',
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
        title="Cancel Workflow"
        buttons={
          <>
            <Button
              disabled={isLoading}
              design={ButtonDesign.Transparent}
              tooltip="Abort"
              onClick={() => {
                setCancelDialogOpen(false);
              }}>
              Abort
            </Button>
            <Button
              disabled={isLoading}
              design={ButtonDesign.Negative}
              tooltip="Cancel Workflow"
              onClick={() => {
                handleCancelWorkflow();
              }}>
              Cancel Workflow
            </Button>
          </>
        }>
        <Text>Do you realy want to cancel this Wokflow?</Text>
      </WeAlertDialog>
    );
  };

  return (
    <PcDynamicPage
      id="admin-workflow-details"
      header={{
        title: 'Workflow details ',
        showBack: true,
        actionSection: (
          <Button
            design={ButtonDesign.Negative}
            title="Cancel Workflow"
            onClick={() => {
              setCancelDialogOpen(true);
            }}>
            Cancel Workflow
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
