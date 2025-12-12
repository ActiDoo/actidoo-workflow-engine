import React from 'react';
import { PcPage } from '@/ui5-components';
import { WeBpmnViewer } from '@/utils/components/WeBpmnViewer';
import { useParams } from 'react-router-dom';
import { BusyIndicator } from '@ui5/webcomponents-react';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import useWorkflowSpec from '@/utils/hooks/useWorkflowSpec';

const AdminWorkflowDiagram: React.FC = () => {
  const { name } = useParams();
  const { dataWorkflowSpec, dataWorkflowSpecItem, loadStateWorkflowSpec, taskStates } = useWorkflowSpec(name);

  return (
    <PcPage
      header={{
        title: `Workflow: ${dataWorkflowSpec ? dataWorkflowSpec.name : ''}`,
        showBack: true
      }}
      innerSpacing={false}>
      {loadStateWorkflowSpec ? (
        <BusyIndicator />
      ) : dataWorkflowSpecItem ? (
        <WeBpmnViewer
          diagramXML={dataWorkflowSpecItem.file_content}
          isAdmin={true}
          workflowName={dataWorkflowSpec ? dataWorkflowSpec.name : ''}
          tasksData={taskStates}
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

export default AdminWorkflowDiagram;
