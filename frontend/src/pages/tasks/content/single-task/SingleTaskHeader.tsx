import React, { useEffect } from 'react';
import {
  Bar,
  BusyIndicator,
  Button,
  ButtonDesign,
  MessageStrip,
  MessageStripDesign,
  Modals,
  Text,
  Title,
  TitleLevel,
} from '@ui5/webcomponents-react';
import { WeDataKey } from '@/store/generic-data/setup';
import { useDispatch, useSelector } from 'react-redux';
import { State } from '@/store';
import { useNavigate, useParams, createSearchParams } from 'react-router-dom';
import { UserTask } from '@/models/models';
import { postRequest, resetStateForKey } from '@/store/generic-data/actions';
import '@ui5/webcomponents-icons/dist/navigation-left-arrow';
import '@ui5/webcomponents-icons/dist/employee-rejections';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { useSelectCurrentWorkflow } from '@/store/generic-data/selectors';
import { handleResponse } from '@/services/HelperService';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';

interface TaskItemHeaderProps {
  task: UserTask;
  reloadTask: () => void;
  backToList: () => void;
}

export const SingleTaskHeader: React.FC<TaskItemHeaderProps> = props => {
  const { workflowId } = useParams();
  const { task } = props;
  const dispatch = useDispatch();
  const navigate = useNavigate();

  const workflowInstance = useSelectCurrentWorkflow(workflowId);
  const assignToMeState = useSelector((state: State) => state.data[WeDataKey.ASSIGN_TASK_TO_ME]);
  const assignTaskToMeLoadState = useSelectUiLoading(WeDataKey.ASSIGN_TASK_TO_ME, 'POST');

  const unassignTaskFromMe = useSelector(
    (state: State) => state.data[WeDataKey.UNASSIGN_TASK_FROM_ME]
  );
  const unassignTaskFromMeLoadState = useSelectUiLoading(WeDataKey.UNASSIGN_TASK_FROM_ME, 'POST');

  const cancelWorkflow = useSelector((state: State) => state.data[WeDataKey.CANCEL_WORKFLOW]);
  const cancelWorkflowLoadState = useSelectUiLoading(WeDataKey.CANCEL_WORKFLOW, 'POST');

  const deleteWorkflow = useSelector((state: State) => state.data[WeDataKey.DELETE_WORKFLOW]);
  const deleteWorkflowLoadState = useSelectUiLoading(WeDataKey.DELETE_WORKFLOW, 'POST');

  const copyInstance = useSelector(
    (state: State) => state.data[WeDataKey.COPY_INSTANCE]
  );
  const copyInstanceLoadState = useSelectUiLoading(WeDataKey.COPY_INSTANCE, 'POST');

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.ASSIGN_TASK_TO_ME,
      assignToMeState?.postResponse,
      'Successfully assigned task',
      'Task could not be assigned to you. Please try again',
      props.reloadTask,
      props.reloadTask
    );
  }, [assignToMeState?.postResponse]);

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.UNASSIGN_TASK_FROM_ME,
      unassignTaskFromMe?.postResponse,
      'Successfully unassigned task',
      'Task could not be unassigned from you. Please try again',
      props.reloadTask,
      props.reloadTask
    );
  }, [unassignTaskFromMe?.postResponse]);

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.CANCEL_WORKFLOW,
      cancelWorkflow?.postResponse,
      'Successfully cancelled workflow',
      'Workflow could not be cancelled. Please try again',
      props.backToList,
      props.reloadTask
    );
  }, [cancelWorkflow?.postResponse]);

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.DELETE_WORKFLOW,
      deleteWorkflow?.postResponse,
      'Successfully deleted workflow',
      'Workflow could not be deleted. Please try again',
      props.backToList,
      props.reloadTask
    );
  }, [deleteWorkflow?.postResponse]);

  useEffect(() => {
    if (!copyInstance?.postResponse) return;

    if (copyInstance.postResponse === 200) {
      const workflowName = copyInstance.data?.workflow_name;
      const taskName = copyInstance.data?.task_name;
      const workflowData = copyInstance.data?.data ?? {};

      if (workflowName) {
        const params = new URLSearchParams();
        params.set('workflow_name', workflowName);
        if (taskName) params.set('task_name', taskName);
        params.set('data', JSON.stringify(workflowData));
        navigate({
          pathname:"/tasks/open/start_workflow_preview",
          search: createSearchParams(params).toString(),
        });
      } else {
        dispatch(addToast(<>Could not prepare workflow copy.</>));
      }
    } else {
      dispatch(addToast(<>Could not copy workflow.</>));
    }
    dispatch(resetStateForKey(WeDataKey.COPY_INSTANCE));
  }, [copyInstance?.postResponse]);

  const handleAssignTaskToMe = (taskId: string): void => {
    dispatch(postRequest(WeDataKey.ASSIGN_TASK_TO_ME, { task_id: taskId }));
  };

  const handleUnassignTaskFromMe = (taskId: string): void => {
    dispatch(postRequest(WeDataKey.UNASSIGN_TASK_FROM_ME, { task_id: taskId }));
  };

  const handleCancelWorkflow = (taskId: string): void => {
    dispatch(postRequest(WeDataKey.CANCEL_WORKFLOW, { task_id: taskId }));
  };

  const showDialog = Modals.useShowDialog();

  const handleDeleteWorkflow = (taskId: string): void => {
    dispatch(postRequest(WeDataKey.DELETE_WORKFLOW, { task_id: taskId }));
  };

  const handleCopyInstance = (): void => {
    if (!workflowInstance?.id) {
      dispatch(addToast(<>Missing workflow identifier.</>));
      return;
    }
    dispatch(postRequest(WeDataKey.COPY_INSTANCE, {}, { workflow_instance_id: workflowInstance.id }));
  };

  return (
    <div className="flex justify-between items-center mb-2 bg-white py-3 px-12 gap-4">
      <div className="flex-1">
        <Text>{workflowInstance?.title}</Text>
        <Title level={TitleLevel.H3}>{task.title}</Title>
      </div>
      {!task.assigned_user && (
        <MessageStrip hideCloseButton={true} design={MessageStripDesign.Warning} className="w-auto">
          Task ist currently not assigned
        </MessageStrip>
      )}
      {task?.state_completed && task.assigned_to_me ? (
        <BusyIndicator active={copyInstanceLoadState} delay={0} className="text-white">
          <Button
            disabled={copyInstanceLoadState}
            design={ButtonDesign.Emphasized}
            onClick={() => {
              handleCopyInstance();
              //alert("The COPY feature is disabled at the moment")
            }}>
            Start new workflow with this data
          </Button>
        </BusyIndicator>
      ) : null}
      {!task.assigned_user ? (
        <BusyIndicator active={assignTaskToMeLoadState} delay={0} className="text-white">
          <Button
            disabled={assignTaskToMeLoadState}
            design={ButtonDesign.Emphasized}
            onClick={() => {
              handleAssignTaskToMe(task.id);
            }}>
            Assign to me
          </Button>
        </BusyIndicator>
      ) : (
        <>
          <Text>
            <span className="text-xs text-neutral-700">Assigned to</span>
            <br />
            {task.assigned_user.full_name}
          </Text>
          {task.can_be_unassigned ? (
            <BusyIndicator active={unassignTaskFromMeLoadState} delay={0} className="">
              <Button
                icon="employee-rejections"
                disabled={unassignTaskFromMeLoadState}
                design={ButtonDesign.Transparent}
                onClick={() => {
                  handleUnassignTaskFromMe(task.id);
                }}>
                Unassign from me
              </Button>
            </BusyIndicator>
          ) : null}
          {task.can_cancel_workflow && !task.can_delete_workflow ? (
            <BusyIndicator active={cancelWorkflowLoadState} delay={0} className="">
              <Button
                icon="employee-rejections"
                disabled={cancelWorkflowLoadState}
                design={ButtonDesign.Transparent}
                onClick={() => {
                  const { close } = showDialog({
                    children: (<span>This will cancel the workflow.<br/><br/>All entered data up to this point will remain visible in the My Workflows overview.</span>),
                    footer: (
                      <Bar
                        startContent={
                          <div>
                            <Button onClick={() => {close();}}>Close Dialog</Button>                          
                          </div>                          
                        }
                        endContent={
                          <div>
                            <Button onClick={() => {handleCancelWorkflow(task.id);close();}}>Cancel Workflow</Button>
                          </div>                          
                        }
                      />
                    ),
                  });
                }}>
                Cancel workflow
              </Button>
            </BusyIndicator>
          ) : null}
          {task.can_delete_workflow ? (
            <BusyIndicator active={deleteWorkflowLoadState} delay={0} className="">
              <Button
                icon="employee-rejections"
                disabled={deleteWorkflowLoadState}
                design={ButtonDesign.Transparent}
                onClick={() => {
                  const { close } = showDialog({
                    children: (<span>This will PERMANENTLY DELETE the workflow.<br/><br/>If you have started this workflow by mistake, you can delete it without any problems.</span>),
                    footer: (
                      <Bar
                        startContent={
                          <div>
                            <Button onClick={() => {close();}}>Close Dialog</Button>                          
                          </div>                          
                        }
                        endContent={
                          <div>
                            <Button onClick={() => {handleDeleteWorkflow(task.id);close();}}>Delete Workflow</Button>
                          </div>                          
                        }
                      />
                    ),
                  });
                }}>
                Delete workflow
              </Button>
            </BusyIndicator>
          ) : null}
        </>
      )}
    </div>
  );
};
