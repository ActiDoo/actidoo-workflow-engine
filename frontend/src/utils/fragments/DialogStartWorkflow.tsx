// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  BusyIndicator,
  Button,
  ButtonDesign,
  Dialog,
  Icon,
  Text,
  Title,
  TitleLevel,
} from '@ui5/webcomponents-react';
import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { getRequest, postRequest, resetStateForKey } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import { State } from '@/store';
import { createPortal } from 'react-dom';
import { addToast } from '@/store/ui/actions';
import { Link, useNavigate } from 'react-router-dom';
import { WeToastContent } from '@/utils/components/WeToast';
import '@ui5/webcomponents-icons/dist/org-chart';
import { WorkflowState } from '@/models/models';
import { environment } from '@/environment';
import { useTranslation } from '@/i18n';

export const DialogStartWorkflow: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [open, setDialogOpen] = useState(false);

  const workflowData = useSelector((state: State) => state.data[WeDataKey.WORKFLOWS]);
  const startData = useSelector((state: State) => state.data[WeDataKey.START_WORKFLOW]);
  const workflowOptions = workflowData?.data?.workflows;

  const loadingState = useSelector((state: State) => state.ui.loading);
  const isLoading =
    loadingState[`${WeDataKey.WORKFLOWS}POST`] || loadingState[`${WeDataKey.START_WORKFLOW}POST`];

  useEffect(() => {
    dispatch(getRequest(WeDataKey.WORKFLOWS));
  }, []);

  useEffect(() => {
    if (startData?.postResponse === 200) {
      dispatch(
        postRequest(WeDataKey.WORKFLOW_INSTANCES_WITH_TASKS, {}, { state: WorkflowState.READY })
      );
      dispatch(addToast(<WeToastContent type="success" text={t('dialogStartWorkflow.success')} />));
      setDialogOpen(false);
      if (startData.data?.workflow_instance_id)
        navigate(`/tasks/open/${startData.data?.workflow_instance_id}`);
    } else if (startData?.postResponse && startData?.postResponse !== 200) {
      dispatch(addToast(<>{t('dialogStartWorkflow.error')}</>));
    }
    dispatch(resetStateForKey(WeDataKey.START_WORKFLOW));
  }, [startData?.postResponse]);

  const environmentInfo =
    environment.environmentLabel ||
    (environment.apiUrl.includes('localhost')
      ? 'LOCALHOST - TESTING' : '');

  return (
    <>
      <span>
        {environmentInfo && (
          <span style={{ color: 'red', paddingRight: 10 }}>{environmentInfo}</span>
        )}
      </span>
      <Button
        design={ButtonDesign.Emphasized}
        icon="add"
        onClick={() => {
          setDialogOpen(true);
        }}>
        {t('dialogStartWorkflow.startWorkflow')}
      </Button>
      {createPortal(
        <Dialog
          open={open}
          header={
            <div className="w-full flex items-center gap-2">
              <Title level={TitleLevel.H5} className="w-full py-2">
                {t('dialogStartWorkflow.header')}
              </Title>
              <Icon
                className="cursor-pointer "
                name="decline"
                onClick={() => {
                  setDialogOpen(false);
                }}
              />
            </div>
          }>
          {workflowOptions ? (
            <BusyIndicator
              active={isLoading}
              size="Medium"
              delay={0}
              className="bg-white/80 w-full">
              <div className="w-full">
                {workflowOptions?.map(w => (
                  <div
                    key={`workflow_${w.name}`}
                    className="flex items-center justify-between py-2 pr-4 w-full">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`workflow-diagram/${w.name}`}
                        onClick={() => {
                          setDialogOpen(false);
                        }}
                        className="inline-flex">
                        <Icon
                          name="org-chart"
                          className="!font-bold !text-brand-primary cursor-pointer"
                        />
                      </Link>
                      <Text>{w.title}</Text>
                    </div>
                    <Text
                      className="!font-bold !text-brand-primary cursor-pointer"
                      onClick={() => {
                        dispatch(postRequest(WeDataKey.START_WORKFLOW, { name: w.name }));
                      }}>
                      {t('dialogStartWorkflow.start')}
                    </Text>
                  </div>
                ))}
              </div>
            </BusyIndicator>
          ) : (
            <Text>{t('dialogStartWorkflow.noneFound')}</Text>
          )}
        </Dialog>,
        document.body
      )}
    </>
  );
};
