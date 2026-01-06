// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import {
  BusyIndicator,
  Button,
  ButtonDesign,
  CheckBox,
  Input,
  InputType,
  Label,
  MessageStrip,
  MessageStripDesign,
  StepInput,
  Text,
  TextArea,
} from '@ui5/webcomponents-react';
import React, { ReactNode, useEffect, useState } from 'react';
import { useTranslation } from '@/i18n';
import { PcMultiInput } from '@/ui5-components/lib/pc-editable-details-section/types/PcMultiInput';
import {
  getErrorMessage,
  getValueAsArray,
  getValueAsBoolean,
  getValueAsNumber,
  getValueAsString,
  getValueState,
  getValueStateMassage,
  hasData,
  setPath,
} from '@/ui5-components/lib/pc-editable-details-section/PcEditableDetailsService';
import { PcSelect } from '@/ui5-components/lib/pc-editable-details-section/types/PcSelect';
import { HTTPValidationError } from '@/ui5-components/models/models';
import {
  PcDetailsSectionItem,
  PcDetailsSectionItemType,
} from '@/ui5-components/lib/pc-editable-details-section/models/PcEditableDetailsSectionModels';
import '@/ui5-components/lib/pc-editable-details-section/PcEditableDetailsSection.scss';

interface PcDetailsSectionProps<T> {
  sections: PcDetailsSectionItem[][][];
  data?: T;
  loading?: boolean;
  isEditable?: boolean;
  onDelete?: () => void;
  onCancel?: () => void;
  onSave?: (obj: T | undefined) => void;
  onEdit?: () => void;
  saveLabel?: string;
  response?: number;
  deleteResponse?: number;
  actionButtonsPosition?: 'bottom' | 'top';
  saveResponse?: number;
  showError?: boolean;
  errorMessage?: string;
  validationError?: HTTPValidationError;
}

export function PcEditableDetailsSection<T>(props: PcDetailsSectionProps<T>): React.ReactElement {
  const { t } = useTranslation();
  const [dataMap, setDataMap] = useState(props.data ?? (undefined as T));
  const [isValid, setIsValid] = useState(false);

  const errorMessage = props.errorMessage
    ? props.errorMessage
    : getErrorMessage(
        props.response,
        props.deleteResponse,
        props.saveResponse,
        props.validationError
      );

  useEffect(() => {
    setIsValid(validate);
  }, [dataMap]);

  useEffect(() => {
    if (props.data) setDataMap(props.data);
  }, [props.data]);

  const handleSave = (): void => {
    if (props.onSave) props.onSave(dataMap);
  };
  const handleCancel = (): void => {
    if (props.onCancel) props.onCancel();
    setDataMap(() => props.data as T);
  };

  const updateData = (key: string, val: any): void => {
    setDataMap(map => {
      const newVal = setPath<T>(map, key, val);
      return newVal;
    });
  };

  const validate = (): boolean =>
    !dataMap
      ? false
      : !props.sections.some(s =>
          s.some(i =>
            i.some(item => (item.required && dataMap ? !hasData<T>(item, dataMap) : false))
          )
        );

  return (
    <>
      {error()}
      {props.actionButtonsPosition === 'top' ? footer(true) : null}

      <div className="flex gap-6 relative flex-wrap">
        {props.sections.map((sectionWrap, i) => (
          <div key={i} className="flex-1 flex gap-6 flex-col">
            {sectionWrap.map((section, j) =>
              section.some(s => s.visible === undefined || s.visible) ? (
                <div key={j} className="p-4 bg-white flex flex-col gap-2">
                  {section.map(item =>
                    item.visible === undefined || item.visible ? (
                      <div key={item.label} className="flex gap-4 items-center">
                        <div className="basis-1/3 max-w-xl">
                          <Label className={item.visible ? 'font-bold italic' : ''}>
                            {item.label}
                            {item.required ? <span className="text-pc-red-500"> *</span> : null}
                          </Label>
                          <br />
                          {item.description ? (
                            <Text className="!text-[12px] !text-pc-gray-400">
                              {item.description}
                            </Text>
                          ) : null}
                        </div>
                        <div className="flex-1">
                          {(() => {
                            switch (item.type) {
                              case PcDetailsSectionItemType.CHECKBOX:
                                return (
                                  <CheckBox
                                    className="w-full"
                                    required={item.required}
                                    disabled={item.readonly ?? !props.isEditable}
                                    checked={getValueAsBoolean<T>(item, dataMap)}
                                    onChange={e => {
                                      item.key && updateData(item.key, e.target.checked);
                                    }}
                                  />
                                );
                              case PcDetailsSectionItemType.TEXTAREA:
                                return (
                                  <TextArea
                                    className="w-full"
                                    required={item.required}
                                    valueState={getValueState<T>(
                                      item,
                                      dataMap,
                                      props.validationError
                                    )}
                                    valueStateMessage={
                                      <Text>
                                        {getValueStateMassage(item, props.validationError)}
                                      </Text>
                                    }
                                    disabled={item.readonly ?? !props.isEditable}
                                    value={getValueAsString<T>(item, dataMap)}
                                    onInput={e => {
                                      item.key && updateData(item.key, e.target.value);
                                    }}
                                    growing={true}
                                    growingMaxLines={10}
                                  />
                                );
                              case PcDetailsSectionItemType.MULTI_INPUT:
                                return (
                                  <PcMultiInput
                                    values={getValueAsArray<T>(item, dataMap)}
                                    disabled={item.readonly ?? !props.isEditable}
                                    valueState={getValueState<T>(item, dataMap)}
                                    valueStateMessage={getValueStateMassage(
                                      item,
                                      props.validationError
                                    )}
                                    onChange={values => {
                                      item.key && updateData(item.key, values);
                                    }}
                                  />
                                );
                              case PcDetailsSectionItemType.SELECT:
                                return (
                                  <PcSelect
                                    item={item}
                                    onChange={val => {
                                      updateData(item.key, val);
                                    }}
                                    isEditable={props.isEditable ?? false}
                                    valueState={getValueState<T>(
                                      item,
                                      dataMap,
                                      props.validationError
                                    )}
                                    valueStateMessage={getValueStateMassage(
                                      item,
                                      props.validationError
                                    )}
                                    selected={getValueAsString<T>(item, dataMap)}
                                  />
                                );
                              case PcDetailsSectionItemType.STEP_INPUT:
                                if (props.isEditable)
                                  return (
                                    <StepInput
                                      className="w-full"
                                      required={item.required}
                                      valueState={getValueState<T>(
                                        item,
                                        dataMap,
                                        props.validationError
                                      )}
                                      valueStateMessage={
                                        <Text>
                                          {getValueStateMassage(item, props.validationError)}
                                        </Text>
                                      }
                                      disabled={item.readonly ?? !props.isEditable}
                                      value={getValueAsNumber<T>(item, dataMap)}
                                      onChange={e => {
                                        item.key && updateData(item.key, e.target.value);
                                      }}
                                    />
                                  );
                                // only disabled
                                return (
                                  <Input
                                    className="w-full"
                                    required={item.required}
                                    valueState={getValueState<T>(
                                      item,
                                      dataMap,
                                      props.validationError
                                    )}
                                    type={InputType.Number}
                                    disabled={true}
                                    value={getValueAsString<T>(item, dataMap)}
                                  />
                                );

                              default:
                                return (
                                  <Input
                                    className="w-full"
                                    required={item.required}
                                    valueState={getValueState<T>(
                                      item,
                                      dataMap,
                                      props.validationError
                                    )}
                                    valueStateMessage={
                                      <Text>
                                        {getValueStateMassage(item, props.validationError)}
                                      </Text>
                                    }
                                    disabled={item.readonly ?? !props.isEditable}
                                    value={getValueAsString<T>(item, dataMap)}
                                    onInput={e => {
                                      item.key && updateData(item.key, e.target.value);
                                    }}
                                  />
                                );
                            }
                          })()}
                        </div>
                      </div>
                    ) : null
                  )}
                </div>
              ) : null
            )}
          </div>
        ))}
        {loading()}
      </div>
      {props.actionButtonsPosition === undefined || props.actionButtonsPosition === 'bottom'
        ? footer()
        : null}
    </>
  );

  function footer(isTop?: boolean): ReactNode | null {
    return props.isEditable ? (
      <div className={`flex gap-4 justify-end ${isTop ? 'mb-4' : 'mt-4'}`}>
        {props.onCancel ? (
          <Button
            className="min-w-[100px]"
            design={ButtonDesign.Transparent}
            disabled={props.loading}
            onClick={handleCancel}>
            {t('common.actions.cancel')}
          </Button>
        ) : null}

        {props.onDelete ? (
          <Button
            className="min-w-[100px]"
            design={ButtonDesign.Negative}
            disabled={props.loading}
            onClick={props.onDelete}>
            {t('common.actions.delete')}
          </Button>
        ) : null}

        {props.onSave ? (
          <Button
            className="min-w-[100px]"
            design={ButtonDesign.Emphasized}
            onClick={handleSave}
            disabled={!isValid || props.loading}>
            {props.saveLabel ?? t('common.actions.save')}
          </Button>
        ) : null}
      </div>
    ) : props.onEdit ? (
      <div className={`flex gap-4 justify-end ${isTop ? 'mb-4' : 'mt-4'}`}>
        <Button
          className="min-w-[100px]"
          design={ButtonDesign.Default}
          onClick={props.onEdit}
          disabled={props.loading}>
          {t('common.actions.edit')}
        </Button>
      </div>
    ) : null;
  }

  function loading(): ReactNode | null {
    return props.loading ? (
      <div className="absolute inset-0 flex items-center justify-center bg-pc-gray-50/50">
        <BusyIndicator active delay={0} />
      </div>
    ) : null;
  }

  function error(): ReactNode | null {
    return (props.response && props.response !== 200) || props.showError ? (
      <MessageStrip design={MessageStripDesign.Negative} className="mb-4" hideCloseButton={true}>
        {errorMessage}
      </MessageStrip>
    ) : null;
  }
}
