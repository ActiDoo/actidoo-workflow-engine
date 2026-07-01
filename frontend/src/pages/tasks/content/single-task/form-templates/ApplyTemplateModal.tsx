// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useRef, useState } from 'react';
import { useDispatch } from 'react-redux';
import _ from 'lodash';
import {
  Bar,
  BusyIndicator,
  Button,
  ButtonDesign,
  CheckBox,
  Input,
  MessageStrip,
  MessageStripDesign,
  Modals,
  Text,
} from '@ui5/webcomponents-react';

import '@ui5/webcomponents-icons/dist/delete';

import WeAlertDialog from '@/utils/components/WeAlertDialog';
import { WeToastContent } from '@/utils/components/WeToast';
import { handleResponse } from '@/services/HelperService';
import { addToast } from '@/store/ui/actions';
import { resetStateForKey } from '@/store/generic-data/actions';
import { WeDataKey } from '@/store/generic-data/setup';
import { useTranslation } from '@/i18n';
import TemplatePreviewList from '@/pages/tasks/content/single-task/form-templates/TemplatePreviewList';
import TemplateStepper from '@/pages/tasks/content/single-task/form-templates/TemplateStepper';
import { useFormTemplates } from '@/pages/tasks/content/single-task/form-templates/useFormTemplates';

interface ApplyTemplateModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId: string;
  jsonschema?: Record<string, any>;
  currentFormData: object;
  onApply: (data: object) => void;
}

const ApplyTemplateModal: React.FC<ApplyTemplateModalProps> = props => {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const showDialog = Modals.useShowDialog();
  const {
    templates,
    listLoading,
    fetchList,
    saveTemplate,
    resolved,
    resolveLoading,
    resolveTemplate,
    resetResolve,
    deleteEntry,
    deleteLoading,
    deleteTemplate,
  } = useFormTemplates(props.taskId);

  const [step, setStep] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [removeDriftFields, setRemoveDriftFields] = useState(false);
  const deletedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (props.isOpen) {
      setStep(1);
      setSelectedId(null);
      setFilter('');
      setRemoveDriftFields(false);
      resetResolve();
      fetchList();
    }
  }, [props.isOpen, fetchList, resetResolve]);

  const visibleTemplates = templates.filter(template =>
    template.name.toLowerCase().includes(filter.trim().toLowerCase())
  );

  useEffect(() => {
    if (deleteEntry?.postResponse === undefined) return;
    handleResponse(
      dispatch,
      WeDataKey.FORM_TEMPLATE_DELETE,
      deleteEntry.postResponse,
      t('formTemplates.delete.success'),
      t('formTemplates.delete.error'),
      () => {
        if (deletedIdRef.current && deletedIdRef.current === selectedId) {
          setSelectedId(null);
          resetResolve();
        }
        fetchList();
      }
    );
    dispatch(resetStateForKey(WeDataKey.FORM_TEMPLATE_DELETE));
  }, [deleteEntry?.postResponse]);

  const selectTemplate = (templateId: string): void => {
    setSelectedId(templateId);
    setRemoveDriftFields(false);
    resetResolve();
    resolveTemplate(templateId);
    setStep(2);
  };

  const confirmDelete = (templateId: string, templateName: string): void => {
    const { close } = showDialog({
      headerText: t('formTemplates.delete.title'),
      children: <Text>{t('formTemplates.delete.message', { name: templateName })}</Text>,
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
                design={ButtonDesign.Negative}
                onClick={() => {
                  deletedIdRef.current = templateId;
                  deleteTemplate(templateId);
                  close();
                }}>
                {t('formTemplates.delete.action')}
              </Button>
            </div>
          }
        />
      ),
    });
  };

  const applyResolved = (): void => {
    if (!resolved) return;
    // Optionally clean the stored template by overwriting it with only the still-applicable fields.
    if (removeDriftFields && resolved.skipped_fields.length > 0) {
      const name = templates.find(template => template.id === selectedId)?.name;
      if (name) saveTemplate(name, resolved.applicable_data);
    }
    props.onApply({ ..._.cloneDeep(props.currentFormData ?? {}), ...resolved.applicable_data });
    dispatch(addToast(<WeToastContent type="success" text={t('formTemplates.apply.success')} />));
    props.onClose();
  };

  const wouldOverwrite = (): boolean => {
    if (!resolved) return false;
    const current = props.currentFormData as Record<string, unknown>;
    return Object.keys(resolved.applicable_data).some(key => {
      const value = current?.[key];
      const isEmpty = value === undefined || value === null || value === '';
      return !isEmpty && !_.isEqual(value, resolved.applicable_data[key]);
    });
  };

  const applySelected = (): void => {
    if (!resolved) return;
    if (!wouldOverwrite()) {
      applyResolved();
      return;
    }
    const { close } = showDialog({
      headerText: t('formTemplates.apply.overwriteTitle'),
      children: <Text>{t('formTemplates.apply.overwriteConfirm')}</Text>,
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
                  applyResolved();
                }}>
                {t('formTemplates.apply.apply')}
              </Button>
            </div>
          }
        />
      ),
    });
  };

  const footer =
    step === 1 ? (
      <Button design={ButtonDesign.Transparent} onClick={props.onClose}>
        {t('common.actions.cancel')}
      </Button>
    ) : (
      <>
        <Button
          design={ButtonDesign.Transparent}
          onClick={() => {
            setStep(1);
          }}>
          {t('formTemplates.apply.back')}
        </Button>
        <Button design={ButtonDesign.Emphasized} disabled={!resolved} onClick={applySelected}>
          {t('formTemplates.apply.apply')}
        </Button>
      </>
    );

  return (
    <WeAlertDialog
      title={t('formTemplates.apply.title')}
      isDialogOpen={props.isOpen}
      setDialogOpen={open => {
        if (!open) props.onClose();
      }}
      buttons={footer}>
      <div className="flex flex-col gap-4 w-full min-w-[28rem]">
        <TemplateStepper
          steps={[t('formTemplates.apply.stepSelect'), t('formTemplates.apply.stepPreview')]}
          current={step}
        />

        {step === 1 ? (
          listLoading ? (
            <div className="flex justify-center py-8">
              <BusyIndicator active delay={0} />
            </div>
          ) : templates.length === 0 ? (
            <MessageStrip design={MessageStripDesign.Information} hideCloseButton>
              {t('formTemplates.apply.empty')}
            </MessageStrip>
          ) : (
            <div className="flex flex-col gap-2">
              <Input
                className="w-full"
                showClearIcon
                placeholder={t('formTemplates.apply.searchPlaceholder')}
                value={filter}
                onInput={event => {
                  setFilter(event.target.value ?? '');
                }}
              />
              {visibleTemplates.length === 0 ? (
                <span className="text-sm text-neutral-500">
                  {t('formTemplates.apply.noResults')}
                </span>
              ) : null}
              <div className="flex flex-col gap-1 max-h-64 overflow-auto">
                {visibleTemplates.map(template => (
                  <div
                    key={template.id}
                    className={`flex items-center justify-between gap-2 rounded px-2 py-1 cursor-pointer ${
                      selectedId === template.id ? 'bg-neutral-100' : 'hover:bg-neutral-50'
                    }`}
                    onClick={() => {
                      selectTemplate(template.id);
                    }}>
                    <div className="flex flex-col min-w-0">
                      <span className="text-sm font-semibold">{template.name}</span>
                      <span className="text-xs text-neutral-500">
                        {new Date(template.updated_at).toLocaleString()}
                      </span>
                    </div>
                    <Button
                      className="shrink-0"
                      design={ButtonDesign.Negative}
                      icon="delete"
                      disabled={deleteLoading && deletedIdRef.current === template.id}
                      onClick={event => {
                        event.stopPropagation();
                        confirmDelete(template.id, template.name);
                      }}
                    />
                  </div>
                ))}
              </div>
            </div>
          )
        ) : resolveLoading ? (
          <div className="flex justify-center py-8">
            <BusyIndicator active delay={0} />
          </div>
        ) : resolved ? (
          <>
            <TemplatePreviewList
              jsonschema={props.jsonschema}
              applicableData={resolved.applicable_data}
              skippedFields={resolved.skipped_fields}
              savedHint={t('formTemplates.apply.appliedTitle')}
              skippedHint={t('formTemplates.preview.skippedHint')}
            />
            {resolved.skipped_fields.length > 0 ? (
              <CheckBox
                className="-ml-[0.6875rem]"
                text={t('formTemplates.apply.removeDriftFields')}
                checked={removeDriftFields}
                onChange={event => {
                  setRemoveDriftFields(event.target.checked);
                }}
              />
            ) : null}
          </>
        ) : null}
      </div>
    </WeAlertDialog>
  );
};

export default ApplyTemplateModal;
