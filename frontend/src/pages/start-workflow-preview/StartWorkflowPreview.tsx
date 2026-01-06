// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useMemo } from 'react';
import {
  BusyIndicator,
  Button,
  ButtonDesign,
  MessageStrip,
  MessageStripDesign,
  Text,
  Title,
  TitleLevel,
} from '@ui5/webcomponents-react';
import { useDispatch, useSelector } from 'react-redux';
import { useLocation } from 'react-router-dom';
import { RJSFSchema, UiSchema } from '@rjsf/utils';
import _ from 'lodash';

import { changeRequiredDefinitionForFieldsWithHideIfDefinition } from '@/services/FeelService';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { WeDataKey } from '@/store/generic-data/setup';
import { postRequest, resetStateForKey } from '@/store/generic-data/actions';
import { State } from '@/store';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';
import TaskForm from '@/rjsf-customs/components/TaskForm';
import { useTranslation } from '@/i18n';

const StartWorkflowPreview: React.FC = () => {
  const { t } = useTranslation();
  const { search } = useLocation();
  const dispatch = useDispatch();

  const searchParams = useMemo(() => new URLSearchParams(search), [search]);
  const workflowName = searchParams.get('workflow_name') ?? '';

  const dataParam = searchParams.get('data');

  const { parsedData, parseError } = useMemo(() => {
    if (!dataParam) return { parsedData: {}, parseError: false };
    try {
      return {
        parsedData: JSON.parse(dataParam) as Record<string, unknown>,
        parseError: false,
      };
    } catch {
      return { parsedData: null, parseError: true };
    }
  }, [dataParam]);

  useEffect(() => {
    dispatch(resetStateForKey(WeDataKey.START_WORKFLOW_PREVIEW));
    return () => {
      dispatch(resetStateForKey(WeDataKey.START_WORKFLOW_PREVIEW));
    };
  }, [dispatch]);

  useEffect(() => {
    if (!workflowName || parseError || parsedData === null) return;
    dispatch(
      postRequest(WeDataKey.START_WORKFLOW_PREVIEW, {
        name: workflowName,
        data: parsedData,
      })
    );
  }, [dispatch, workflowName, parseError, parsedData]);

  const previewState = useSelector(
    (state: State) => state.data[WeDataKey.START_WORKFLOW_PREVIEW]
  );
  const previewLoading = useSelectUiLoading(WeDataKey.START_WORKFLOW_PREVIEW, 'POST');
  const startLoading = useSelectUiLoading(WeDataKey.START_WORKFLOW, 'POST');

  useEffect(() => {
    if (
      previewState?.postResponse &&
      previewState.postResponse !== 200
    ) {
      dispatch(addToast(<WeToastContent type="error" text={t('workflowPreview.loadError')} />));
    }
  }, [previewState?.postResponse, dispatch]);

  const previewTask = previewState?.data?.task;

  const previewWorkflowTitle = previewState?.data?.title ?? '';
  
  const { jsonschema, uiSchema } = useMemo(() => {
    if (!previewTask?.jsonschema || !previewTask?.uischema) {
      return { jsonschema: undefined, uiSchema: undefined };
    }
    const schemaClone = _.cloneDeep(previewTask.jsonschema) as RJSFSchema;
    const uiSchemaClone = _.cloneDeep(
      previewTask.uischema
    ) as UiSchema<any, RJSFSchema, any>;
    changeRequiredDefinitionForFieldsWithHideIfDefinition(schemaClone, uiSchemaClone);
    return { jsonschema: schemaClone, uiSchema: uiSchemaClone };
  }, [previewTask]);

  const formData = useMemo(() => previewTask?.data ?? {}, [previewTask]);

  const handleStartWorkflow = (): void => {
    if (!workflowName || parsedData === null) return;
    dispatch(
      postRequest(WeDataKey.START_WORKFLOW, {
        name: workflowName,
        data: parsedData,
      })
    );
  };

  const cannotStartWorkflow =
    !workflowName || parseError || parsedData === null || !previewTask;

  return (
    <div className="pl-2">
      <div className="mb-2 bg-white py-3 px-12 gap-4">
        <div className="flex-1">
          <Text>{previewWorkflowTitle}</Text>
          <Title level={TitleLevel.H3}>{previewTask?.title ?? ''}</Title>
          <MessageStrip design={MessageStripDesign.Information} hideCloseButton={true}>
            {t('workflowPreview.previewInfo')}
          </MessageStrip>
        </div>
      </div>
    
      {parseError ? (
        <div className="mt-2">
          <MessageStrip design={MessageStripDesign.Negative} hideCloseButton={true}>
            {t('workflowPreview.parseError')}
          </MessageStrip>
        </div>
      ) : null}

      {previewLoading ? (
        <div className="flex justify-center items-center py-16">
          <BusyIndicator active delay={0} />
        </div>
      ) : previewTask && jsonschema && uiSchema ? (
        <div className="bg-white pt-4 px-12 pc-form pb-16 mt-2">
          <TaskForm
            key={previewTask.id}
            formData={formData}
            schema={jsonschema}
            uiSchema={uiSchema}
            disabled
            showErrorList={false}
            formContext={{
              formData,
              schema: previewTask.jsonschema,
              uiSchema: previewTask.uischema,
            }}
          />

          <div className="mt-16 flex flex-row justify-end">
            <MessageStrip className="max-w-4xl" design={MessageStripDesign.Information} hideCloseButton={true}>
              {t('workflowPreview.startInfo')}
            </MessageStrip>
          </div>

          <div className="flex flex-row flex-wrap gap-2 mt-2">
            <div className="flex-1"></div>
            <BusyIndicator active={startLoading} delay={0}>
              <Button
                design={ButtonDesign.Emphasized}
                disabled={startLoading || cannotStartWorkflow}
                onClick={handleStartWorkflow}>
                {t('workflowPreview.startWithData')}
              </Button>
            </BusyIndicator>
          </div>
        </div>
      ) : (
        <div className="mt-6">
          <MessageStrip design={MessageStripDesign.Negative} hideCloseButton={true}>
            {t('workflowPreview.unavailable')}
          </MessageStrip>
        </div>
      )}


    </div>
  );
};

export default StartWorkflowPreview;
