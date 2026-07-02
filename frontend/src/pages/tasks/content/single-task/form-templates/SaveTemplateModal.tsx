// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useState } from 'react';
import { useDispatch } from 'react-redux';
import {
  Bar,
  BusyIndicator,
  Button,
  ButtonDesign,
  Input,
  InputDomRef,
  MessageStrip,
  MessageStripDesign,
  Modals,
  SuggestionItem,
  Text,
  Ui5CustomEvent,
} from '@ui5/webcomponents-react';
import Suggestions from '@ui5/webcomponents/dist/features/InputSuggestions.js';
import { InputSuggestionItemSelectEventDetail } from '@ui5/webcomponents/dist/Input';

import WeAlertDialog from '@/utils/components/WeAlertDialog';
import { handleResponse } from '@/services/HelperService';
import { resetStateForKey } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import { useTranslation } from '@/i18n';
import { FormTemplateSummary } from '@/models/models';
import TemplatePreviewList from '@/pages/tasks/content/single-task/form-templates/TemplatePreviewList';
import TemplateStepper from '@/pages/tasks/content/single-task/form-templates/TemplateStepper';
import { useFormTemplates } from '@/pages/tasks/content/single-task/form-templates/useFormTemplates';

interface SaveTemplateModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  formData: object;
  templates: FormTemplateSummary[];
  jsonschema?: Record<string, any>;
  onSaved: () => void;
}

const SaveTemplateModal: React.FC<SaveTemplateModalProps> = props => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const showDialog = Modals.useShowDialog();
  const {
    saveTemplate,
    saveEntry,
    saveLoading,
    previewTemplate,
    previewResult,
    previewError,
    previewLoading,
  } = useFormTemplates(props.taskId);
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');

  useEffect(() => {
    void Suggestions.init();
  }, []);

  useEffect(() => {
    if (props.isOpen) {
      setStep(1);
      setName('');
      dispatch(resetStateForKey(WeDataKey.FORM_TEMPLATE_SAVE));
      previewTemplate(props.formData);
    }
  }, [props.isOpen]);

  useEffect(() => {
    if (saveEntry?.postResponse === undefined) return;
    handleResponse(
      dispatch,
      WeDataKey.FORM_TEMPLATE_SAVE,
      saveEntry.postResponse,
      t('formTemplates.save.success'),
      t('formTemplates.save.error'),
      () => {
        props.onSaved();
        props.onClose();
      }
    );
    dispatch(resetStateForKey(WeDataKey.FORM_TEMPLATE_SAVE));
  }, [saveEntry?.postResponse]);

  const trimmed = name.trim();
  const isDuplicate = props.templates.some(
    template => template.name.toLowerCase() === trimmed.toLowerCase()
  );

  const handleSaveClick = (): void => {
    if (!isDuplicate) {
      saveTemplate(trimmed, props.formData);
      return;
    }
    const { close } = showDialog({
      headerText: t('formTemplates.save.overwriteTitle'),
      children: <Text>{t('formTemplates.save.overwriteHint')}</Text>,
      footer: (
        <Bar
          endContent={
            <div className="flex gap-2">
              <Button
                design={ButtonDesign.Transparent}
                onClick={() => {
                  close();
                }}>
                {t('common.actions.cancel')}
              </Button>
              <Button
                design={ButtonDesign.Emphasized}
                onClick={() => {
                  close();
                  saveTemplate(trimmed, props.formData);
                }}>
                {t('formTemplates.save.overwrite')}
              </Button>
            </div>
          }
        />
      ),
    });
  };

  const footer =
    step === 1 ? (
      <>
        <Button design={ButtonDesign.Transparent} onClick={props.onClose}>
          {t('common.actions.cancel')}
        </Button>
        <Button
          design={ButtonDesign.Emphasized}
          disabled={previewLoading}
          onClick={() => {
            setStep(2);
          }}>
          {t('formTemplates.save.next')}
        </Button>
      </>
    ) : (
      <>
        <Button
          design={ButtonDesign.Transparent}
          onClick={() => {
            setStep(1);
          }}>
          {t('formTemplates.save.back')}
        </Button>
        <Button
          design={ButtonDesign.Emphasized}
          disabled={!trimmed || saveLoading}
          onClick={handleSaveClick}>
          {isDuplicate ? t('formTemplates.save.overwrite') : t('formTemplates.save.save')}
        </Button>
      </>
    );

  return (
    <WeAlertDialog
      title={t('formTemplates.save.title')}
      isDialogOpen={props.isOpen}
      setDialogOpen={open => {
        if (!open) props.onClose();
      }}
      buttons={footer}>
      <div className="flex flex-col gap-4 w-full min-w-[28rem]">
        <TemplateStepper
          steps={[t('formTemplates.save.stepPreview'), t('formTemplates.save.stepName')]}
          current={step}
        />

        {step === 1 ? (
          previewLoading ? (
            <div className="flex justify-center py-8">
              <BusyIndicator active delay={0} />
            </div>
          ) : previewError ? (
            <MessageStrip design={MessageStripDesign.Negative} hideCloseButton>
              {t('formTemplates.apply.loadError')}
            </MessageStrip>
          ) : previewResult ? (
            <TemplatePreviewList
              jsonschema={props.jsonschema}
              applicableData={previewResult.applicable_data}
              skippedFields={previewResult.skipped_fields}
              savedHint={t('formTemplates.save.previewTitle')}
              skippedHint={t('formTemplates.save.skippedHint')}
            />
          ) : null
        ) : (
          <Input
            className="w-full"
            value={name}
            showSuggestions
            noTypeahead
            showClearIcon
            placeholder={t('formTemplates.save.namePlaceholder')}
            onInput={event => {
              setName(event.currentTarget?.value ?? '');
            }}
            onSuggestionItemSelect={(
              event: Ui5CustomEvent<InputDomRef, InputSuggestionItemSelectEventDetail>
            ) => {
              setName(event.detail.item.text ?? '');
            }}>
            {props.templates.map(template => (
              <SuggestionItem key={template.id} text={template.name} />
            ))}
          </Input>
        )}
      </div>
    </WeAlertDialog>
  );
};

export default SaveTemplateModal;
