// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useRef, useState } from 'react';
import {
  BusyIndicator,
  Button,
  ButtonDesign,
  MessageStrip,
  MessageStripDesign,
  TextArea,
} from '@ui5/webcomponents-react';

import '@ui5/webcomponents-icons/dist/syntax';
import '@ui5/webcomponents-icons/dist/edit';
import '@ui5/webcomponents-icons/dist/tree';
import { useDispatch, useSelector } from 'react-redux';
import { WeDataKey } from '@/store/generic-data/setup';
import { postRequest } from '@/store/generic-data/actions';
import { TextAreaDomRef } from '@ui5/webcomponents-react/dist/webComponents/TextArea';
import { State } from '@/store';
import { WeEmptySection } from '@/utils/components/WeEmptySection';
import { handleResponse } from '@/services/HelperService';
import { useSelectUiLoading } from '@/store/ui/selectors';
import { useTranslation } from '@/i18n';
import { WeJsonTree } from '@/utils/components/WeJsonTree';

interface AdminJsonSchemaSectionProps {
  taskId?: string;
  data?: object;
}

const WeEditableDataSection: React.FC<AdminJsonSchemaSectionProps> = props => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const textAreaRef = useRef<TextAreaDomRef | null>(null);
  const replaceTaskData = useSelector(
    (state: State) => state.data[WeDataKey.ADMIN_REPLACE_TASK_DATA]
  );
  const saveLoadingState = useSelectUiLoading(WeDataKey.ADMIN_REPLACE_TASK_DATA, 'POST');
  const getJsonString = (): string => JSON.stringify(props?.data, undefined, 2);

  const [value, setValue] = useState(getJsonString());
  const [showError, setShowError] = useState(false);
  const [showTree, setShowTree] = useState(false);

  useEffect(() => {
    handleResponse(
      dispatch,
      WeDataKey.ADMIN_REPLACE_TASK_DATA,
      replaceTaskData?.postResponse,
      t('editableData.saveSuccess'),
      t('editableData.saveError')
    );
  }, [replaceTaskData?.postResponse]);

  useEffect(() => {
    setValue(getJsonString());
  }, [props?.data]);

  const handleSaveChanges = (): void => {
    const data = textAreaRef?.current?.value;
    dispatch(
      postRequest(WeDataKey.ADMIN_REPLACE_TASK_DATA, {
        task_id: props.taskId,
        data: JSON.parse(data ?? ''),
      })
    );
  };

  const validateValue = (val?: string): void => {
    try {
      JSON.parse(val ?? '');
      setShowError(false);
    } catch (e) {
      setShowError(true);
    }
  };

  const handleReset = (): void => {
    setValue(getJsonString());
    setShowError(false);
  };

  return props?.data && Object.keys(props.data).length > 1 ? (
    <>
      {showTree ? (
        <>
          <WeJsonTree data={props.data} />
          <div className="flex justify-end mt-2">
            <Button
              icon="edit"
              design={ButtonDesign.Transparent}
              onClick={() => {
                setShowTree(false);
              }}>
              {t('editableData.editJson')}
            </Button>
          </div>
        </>
      ) : (
        <>
          <TextArea
            className="mt-2"
            rows={20}
            value={value}
            ref={textAreaRef}
            onInput={e => {
              validateValue(e.target.value);
              if (e.target.value) setValue(e.target.value);
            }}
          />
          <div className="flex justify-end mt-2 gap-2">
            {showError ? (
              <MessageStrip
                design={MessageStripDesign.Warning}
                hideCloseButton
                className="max-w-[400px]">
                {t('editableData.noValidJson')}
              </MessageStrip>
            ) : null}
            <Button
              icon="tree"
              design={ButtonDesign.Transparent}
              onClick={() => {
                setShowTree(true);
              }}>
              {t('editableData.treeView')}
            </Button>
            <Button
              disabled={getJsonString() === value}
              design={ButtonDesign.Transparent}
              onClick={() => {
                handleReset();
              }}>
              {t('editableData.reset')}
            </Button>
            <BusyIndicator active={saveLoadingState} delay={0} className="text-white">
              <Button
                // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- logical OR between booleans
                disabled={saveLoadingState || showError}
                design={ButtonDesign.Emphasized}
                onClick={() => {
                  handleSaveChanges();
                }}>
                {t('editableData.saveChanges')}
              </Button>
            </BusyIndicator>
          </div>
        </>
      )}
    </>
  ) : (
    <div className="bg-neutral-50">
      <WeEmptySection
        icon="syntax"
        title={t('common.messages.noDataDefined')}
        text={t('common.messages.objectIsEmpty')}
      />
    </div>
  );
};
export default WeEditableDataSection;
