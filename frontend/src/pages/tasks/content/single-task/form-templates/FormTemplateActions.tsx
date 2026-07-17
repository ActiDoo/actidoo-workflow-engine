// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useState } from 'react';
import { Button, ButtonDesign } from '@ui5/webcomponents-react';

import '@ui5/webcomponents-icons/dist/save';
import '@ui5/webcomponents-icons/dist/download';

import { useTranslation } from '@/i18n';
import SaveTemplateModal from '@/pages/tasks/content/single-task/form-templates/SaveTemplateModal';
import ApplyTemplateModal from '@/pages/tasks/content/single-task/form-templates/ApplyTemplateModal';
import { useFormTemplates } from '@/pages/tasks/content/single-task/form-templates/useFormTemplates';

interface FormTemplateActionsProps {
  taskId: string;
  jsonschema?: Record<string, any>;
  formData: object;
  onApply: (data: object) => void;
}

const FormTemplateActions: React.FC<FormTemplateActionsProps> = props => {
  const { t } = useTranslation();
  const { templates, fetchList } = useFormTemplates(props.taskId);
  const [saveOpen, setSaveOpen] = useState(false);
  const [applyOpen, setApplyOpen] = useState(false);

  return (
    <div className="flex justify-end gap-2 max-w-7xl pt-2">
      <Button
        design={ButtonDesign.Transparent}
        icon="save"
        onClick={() => {
          fetchList();
          setSaveOpen(true);
        }}>
        {t('formTemplates.saveAction')}
      </Button>
      <Button
        design={ButtonDesign.Transparent}
        icon="download"
        onClick={() => {
          setApplyOpen(true);
        }}>
        {t('formTemplates.applyAction')}
      </Button>

      {saveOpen ? (
        <SaveTemplateModal
          isOpen={saveOpen}
          onClose={() => {
            setSaveOpen(false);
          }}
          taskId={props.taskId}
          formData={props.formData}
          templates={templates}
          jsonschema={props.jsonschema}
          onSaved={fetchList}
        />
      ) : null}
      {applyOpen ? (
        <ApplyTemplateModal
          isOpen={applyOpen}
          onClose={() => {
            setApplyOpen(false);
          }}
          taskId={props.taskId}
          jsonschema={props.jsonschema}
          currentFormData={props.formData}
          onApply={props.onApply}
        />
      ) : null}
    </div>
  );
};

export default FormTemplateActions;
