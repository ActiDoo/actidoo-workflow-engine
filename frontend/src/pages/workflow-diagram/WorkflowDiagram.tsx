import React from 'react';
import { PcPage } from '@/ui5-components';
import { WeBpmnViewer } from '@/utils/components/WeBpmnViewer';
import { useParams } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { BusyIndicator, Button, ButtonDesign } from '@ui5/webcomponents-react';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { postRequest } from '@/store/generic-data/actions';
import useWorkflowSpec from '@/utils/hooks/useWorkflowSpec';

const WorkflowDiagram: React.FC = () => {
  const { name } = useParams();
  const dispatch = useDispatch()
  const { dataWorkflowSpec, dataWorkflowSpecItem, loadStateWorkflowSpec } = useWorkflowSpec(name);

  return (
    <PcPage
      header={{
        title: `Workflow: ${dataWorkflowSpec ? dataWorkflowSpec.name : ''}`,
        actionSection: (
          <Button
            design={ButtonDesign.Emphasized}
            onClick={() => {
              dispatch(postRequest(WeDataKey.START_WORKFLOW, { name }));
            }}>
            Start this workflow
          </Button>
        ),
      }}
      innerSpacing={false}>
      {loadStateWorkflowSpec ? (
        <BusyIndicator />
      ) : dataWorkflowSpecItem ? (
        <WeBpmnViewer
          diagramXML={dataWorkflowSpecItem.file_content}
          isAdmin={false}
        />
      ) : dataWorkflowSpec ? (
        <WeEmptySection
          icon={'org-chart'}
          title={'Workflow specification not found'}
          text={`There is no workflow specification for this workflow`}
        />
      ) : (
        <WeEmptySection
          icon={'org-chart'}
          title={'Workflow not found'}
          text={'There is no workflow with this name'}
        />
      )}
    </PcPage>
  );
};
export default WorkflowDiagram;
