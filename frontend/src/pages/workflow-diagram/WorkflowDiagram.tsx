// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

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
import { useTranslation } from '@/i18n';

const WorkflowDiagram: React.FC = () => {
  const { t } = useTranslation();
  const { name } = useParams();
  const dispatch = useDispatch()
  const { dataWorkflowSpec, dataWorkflowSpecItem, loadStateWorkflowSpec } = useWorkflowSpec(name);

  return (
    <PcPage
      header={{
        title: t('workflowDiagram.workflowTitle', { name: dataWorkflowSpec ? dataWorkflowSpec.name : '' }),
        actionSection: (
          <Button
            design={ButtonDesign.Emphasized}
            onClick={() => {
              dispatch(postRequest(WeDataKey.START_WORKFLOW, { name }));
            }}>
            {t('workflowDiagram.startThisWorkflow')}
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
export default WorkflowDiagram;
