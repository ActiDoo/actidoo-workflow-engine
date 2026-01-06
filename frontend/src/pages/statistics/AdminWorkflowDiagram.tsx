// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { PcPage } from '@/ui5-components';
import { WeBpmnViewer } from '@/utils/components/WeBpmnViewer';
import { useParams } from 'react-router-dom';
import { BusyIndicator } from '@ui5/webcomponents-react';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import useWorkflowSpec from '@/utils/hooks/useWorkflowSpec';
import { useTranslation } from '@/i18n';

const AdminWorkflowDiagram: React.FC = () => {
  const { t } = useTranslation();
  const { name } = useParams();
  const { dataWorkflowSpec, dataWorkflowSpecItem, loadStateWorkflowSpec, taskStates } = useWorkflowSpec(name);

  return (
    <PcPage
      header={{
        title: t('workflowDiagram.workflowTitle', { name: dataWorkflowSpec ? dataWorkflowSpec.name : '' }),
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
          title={t('workflowDiagram.specificationNotFoundTitle')}
          text={t('workflowDiagram.specificationNotFoundText')}
        />
      ) : (
        <WeEmptySection
          icon={'org-chart'}
          title={t('workflowDiagram.workflowNotFoundTitle')}
          text={t('workflowDiagram.workflowNotFoundText')}
        />
      )}
    </PcPage>
  );
};

export default AdminWorkflowDiagram;
