// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { ReactElement, useEffect, useMemo, useState } from 'react';
import { useDispatch } from 'react-redux';
import { useLocation, useParams } from 'react-router-dom';
import {
  Bar,
  Button,
  ButtonDesign,
  Icon,
  Label,
  Modals,
  Table,
  TableCell,
  TableColumn,
  TableRow,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/copy';
import '@ui5/webcomponents-icons/dist/duplicate';
import {
  ArrayFieldTemplateProps,
  FormContextType,
  getUiOptions,
  RJSFSchema,
  StrictRJSFSchema,
} from '@rjsf/utils';
import { InterpreterContext, unaryTest } from 'feelin';
import { fetchPost } from '@/ui5-components';
import { useTranslation } from '@/i18n';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';
import { getApiUrl } from '@/services/ApiService';
import {
  buildEvaluationContext,
  buildMaskedParentContext,
  resolveHiddenFields,
} from '@/services/feelContext';
import { PcValueLabelItem } from '@/models/models';
import {
  isAttachmentSingleSchema,
  stripAttachmentPayload,
} from '@/rjsf-customs/custom-fields/multiFileField/attachments';
import _ from 'lodash';

type OverviewLabels = Record<string, Record<string, string>>;

const isDynamicSelect = (uiSchema: any): boolean =>
  ['SelectDynamic', 'MultiSelectDynamic'].includes(uiSchema?.['ui:widget']);

// Resolve each selected value in its own row, including nested lists. A value may
// have different labels in two rows, so index the labels by the complete path.
const loadOverviewLabels = async (
  rowUiSchema: any,
  rows: any[],
  arrayPath: Array<string | number>,
  taskId: string | undefined,
  formData: unknown
): Promise<OverviewLabels> => {
  if (!taskId) return {};
  const labels: OverviewLabels = {};
  await Promise.all(
    rows.flatMap((row, rowIndex) =>
      Object.entries(rowUiSchema ?? {}).map(async ([key, config]: [string, any]) => {
        const propertyPath = [...arrayPath, rowIndex, key];
        const value = row?.[key];
        if (isDynamicSelect(config)) {
          const values = (Array.isArray(value) ? value : [value]).filter(
            item => item !== undefined && item !== null && item !== ''
          );
          if (!values.length) return;
          try {
            const response = await fetchPost(getApiUrl('user/search_property_options'), {
              task_id: taskId,
              property_path: propertyPath,
              search: '',
              include_value: values.length === 1 ? values[0] : values,
              form_data: stripAttachmentPayload(formData),
            });
            labels[JSON.stringify(propertyPath)] = Object.fromEntries(
              ((response?.data?.options ?? []) as PcValueLabelItem[]).map(option => [
                String(option.value),
                `${option.label} (ID: ${option.value})`,
              ])
            );
          } catch (error) {
            console.error('Failed to fetch dynamic select labels for overview', error);
          }
        } else if (config?.items && Array.isArray(value)) {
          Object.assign(
            labels,
            await loadOverviewLabels(config.items, value, propertyPath, taskId, formData)
          );
        }
      })
    )
  );
  return labels;
};

const evaluateHideIf = (expression: string, context: InterpreterContext | undefined): boolean => {
  try {
    return unaryTest(expression, { ...(context ?? {}) });
  } catch {
    return false;
  }
};

export default function CustomArrayFieldTemplate<
  T = any,
  S extends StrictRJSFSchema = RJSFSchema,
  F extends FormContextType = any
>(props: ArrayFieldTemplateProps<T, S, F>): ReactElement | null {
  // console.log("**** Array Field Template ********************************************************************************************")
  // console.log(props)

  const uiOptions = getUiOptions<T, S, F>(props.uiSchema);
  const { t } = useTranslation();
  const dispatch = useDispatch();

  const location = useLocation();
  const { taskId } = useParams();
  const effectiveTaskId = taskId ?? (props.registry as any)?.formContext?.taskId;
  const [overviewLoading, setOverviewLoading] = useState(false);
  const itemUiSchema = (props.uiSchema as any)?.items;
  useEffect(() => {
    // DURING THE FIRST RENDER -> ADD THE MINIMUM ITEMS, WHICH SHALL BE VISIBLE

    // check our uischema expectation and only do it on the open tasks page (not later on, when the workflow is completed)
    const defaultRepetitionsRaw = uiOptions?.defaultRepetitions;
    const defaultRepetitions =
      typeof defaultRepetitionsRaw === 'number' ? defaultRepetitionsRaw : 0;

    if (defaultRepetitions > 0 && location?.pathname?.includes('/tasks/open/')) {
      // uiOptions["defaultRepetitions"] -> the initial number of displayed items in a dynamic list as the user configured it
      // props.schema.minItems -> the minimum number of items the user has to submit
      // props.items -> the actual display items how RJSF calculated it (unfortunately based on props.schema.minItems)

      // So, it can be that the user does NOT HAVE to submit any item (props.schema.minItems = 0), then RJSF has calculated
      // that no item shall be displayed initially (props.items == empty array), but actually the list
      // is configured to show at least 1 item at the beginning ( uiOptions["defaultRepetitions"]= 1), but which can be
      // deleted by the user, because he does NOT HAVE to submit it.
      // In this case we now insert the missing number of items:

      const currentItems = props.items?.length ?? 0;
      for (let i = 0; i < defaultRepetitions - currentItems; i++) {
        // add as many items as needed.
        // Fake the adding by simulating an ADD click, because ArrayField.tsx from RJSF will take care of it
        // (no need to reimplement the code)
        // I insert a Dummy MouseEvent although an undefined is also handled by the code,
        // but to avoid potential crashes in future RJSF updates when an undefined is no longer accepted.
        // (see onAddClick method in RJSF's ArrayField.tsx)

        setTimeout(() => {
          // With the setTimeout trick we do it asynchronously: otherwise when adding more than 1 item, the next onAddClick() will not be handled properly and no item is added.
          // We also have to have a delay between each inAddClick, therefore each gets 100ms to complete, before the next onAddClick gets executed.
          // (10 ms was not enough, some items were missing but with 100ms we were good, even for adding 10 items in case of the big Workflow)
          props.onAddClick(new MouseEvent('Dummy'));
        }, 100 + i * 100);

        // console.log("############# ADD")
      }
    }
  }, []);

  // console.log(props.items.length)
  const showDialog = Modals.useShowDialog();
  const items = props.schema.items as unknown as {
    properties: Record<string, { title: string }>;
  };

  const formContextSignature = JSON.stringify(
    (props.registry as any)?.formContext?.formData ?? null
  );
  const rootData = (props.registry as any)?.formContext?.formData;
  const rootUiSchema = (props.registry as any)?.formContext?.uiSchema;
  const maskedRootContext = useMemo(
    () =>
      rootUiSchema
        ? resolveHiddenFields(rootUiSchema, rootData, evaluateHideIf).maskedContext ?? rootData
        : rootData,
    [formContextSignature, rootUiSchema]
  );

  // The overview must show exactly what the form shows, so it evaluates every row's
  // hide-if with the same context the row's fields were rendered with (see
  // CustomArraySchemaField). Rows of one list can differ: a field hidden in row 1 can
  // be visible in row 2.
  const resolveHiddenKeysPerRow = (
    rowUiSchema: any,
    rows: any[],
    arrayId: string
  ): Array<Set<string>> =>
    rows.map((row, index) => {
      const parent = buildMaskedParentContext(
        rootData,
        rootUiSchema,
        `${arrayId}_${index}`,
        maskedRootContext,
        evaluateHideIf
      );
      const evalContext = buildEvaluationContext(maskedRootContext, row, parent);
      return resolveHiddenFields(rowUiSchema, evalContext, evaluateHideIf).hiddenFields;
    });

  const cellText = (
    property: any,
    raw: unknown,
    fieldUiSchema: any,
    fieldPath: Array<string | number>,
    labels: OverviewLabels
  ): string | undefined => {
    let val: any = raw;
    if (isDynamicSelect(fieldUiSchema)) {
      const mapping = labels[JSON.stringify(fieldPath)] ?? {};
      const label = (value: unknown): string =>
        value == null ? '' : mapping[String(value)] ?? String(value);
      return Array.isArray(val) ? val.map(label).join(', ') : label(val);
    }
    if (property?.oneOf) {
      const match = property.oneOf.find((o: any) => o.const === val);
      if (match) val = match.title;
    }
    if (typeof val === 'boolean') return val ? 'Yes' : 'No';
    if (property?.type === 'array' && Array.isArray(val)) return undefined;
    return val == null ? '' : String(val);
  };

  const copyColumn = (texts: string[]): void => {
    const text = texts.map(value => value.replace(/[\t\r\n]+/g, ' ')).join('\r\n');
    navigator.clipboard.writeText(text).then(
      () => dispatch(addToast(<WeToastContent text={t('listOverview.columnCopied')} />)),
      () => dispatch(addToast(<WeToastContent text={t('listOverview.copyFailed')} />))
    );
  };

  const renderTable = (
    items: any,
    dataArray: any[],
    rowUiSchema: any,
    arrayId: string,
    arrayPath: Array<string | number>,
    labels: OverviewLabels
  ): JSX.Element => {
    const properties = items?.properties ?? {};
    const rows = dataArray ?? [];
    const hiddenKeysPerRow = resolveHiddenKeysPerRow(rowUiSchema, rows, arrayId);

    // A text view carries no data ("null" type), and a field every row hides carries
    // no visible one, so neither earns a column.
    const columnKeys = Object.keys(properties).filter(
      key =>
        properties[key]?.type !== 'null' &&
        (!rows.length || hiddenKeysPerRow.some(hiddenKeys => !hiddenKeys.has(key)))
    );

    const tableColumns = columnKeys.map((key, index) => (
      <TableColumn key={`column-${index}`}>
        <div className="flex items-center gap-1">
          <Label>{properties[key].title}</Label>
          {(properties[key]?.type !== 'array' || isDynamicSelect(rowUiSchema?.[key])) &&
            !isAttachmentSingleSchema(properties[key]) && (
              <Icon
                name="copy"
                accessibleName={t('listOverview.copyColumn')}
                interactive
                showTooltip
                className="!w-3.5 !h-3.5 shrink-0 cursor-pointer !text-brand-primary"
                onClick={() => {
                  copyColumn(
                    rows.map((data, rowIndex) =>
                      hiddenKeysPerRow[rowIndex]?.has(key)
                        ? ''
                        : cellText(
                            properties[key],
                            data[key],
                            rowUiSchema?.[key],
                            [...arrayPath, rowIndex, key],
                            labels
                          ) ?? ''
                    )
                  );
                }}
              />
            )}
        </div>
      </TableColumn>
    ));

    const isPdfArray = (val: any) => {
      return (
        Array.isArray(val) && val.length > 0 && val.some(item => item.filename?.includes('.pdf'))
      );
    };

    const tableRows = rows.map((data, rowIndex) => (
      <TableRow key={`row-${rowIndex}`}>
        {columnKeys.map(key => {
          if (hiddenKeysPerRow[rowIndex]?.has(key)) {
            return <TableCell key={`cell-${rowIndex}-${key}`} />;
          }

          const val = data[key];
          const property = properties[key];

          // Check if the value is an array containing PDFs
          if (isPdfArray(val)) {
            return (
              <TableCell key={`cell-${rowIndex}-${key}`}>
                {val.map((file: any, index: number) => (
                  <div key={index}>{file.filename}</div> // Display only the filename
                ))}
              </TableCell>
            );
          }

          const text = cellText(
            property,
            val,
            rowUiSchema?.[key],
            [...arrayPath, rowIndex, key],
            labels
          );

          // Handle nested arrays recursively
          if (text === undefined) {
            return (
              <TableCell key={`cell-${rowIndex}-${key}`}>
                {renderTable(
                  property.items,
                  val,
                  rowUiSchema?.[key]?.items,
                  `${arrayId}_${rowIndex}_${key}`,
                  [...arrayPath, rowIndex, key],
                  labels
                )}
              </TableCell>
            );
          }

          return (
            <TableCell key={`cell-${rowIndex}-${key}`}>
              <Label>{text}</Label>
            </TableCell>
          );
        })}
      </TableRow>
    ));

    return <Table columns={<>{tableColumns}</>}>{tableRows}</Table>;
  };

  const allowAddRemove = String((uiOptions as any)?.arrayAllowAddRemove ?? 'True') === 'True';

  // Read-only: fetch form data with hidden fields stripped (hide-if is server-side only);
  // fieldPathId.path locates this (possibly nested) list in the cleaned data. Falls back to raw.
  const openOverview = async (): Promise<void> => {
    setOverviewLoading(true);
    let dataArray = (props.formData as any[]) ?? [];
    const fullFormData = (props.registry as any)?.formContext?.formData;
    if (effectiveTaskId && fullFormData) {
      try {
        const response = await fetchPost(getApiUrl('user/strip_hidden_fields'), {
          task_id: effectiveTaskId,
          form_data: fullFormData,
        });
        const cleaned = response?.data?.form_data;
        const slice = cleaned ? _.get(cleaned, props.fieldPathId?.path as any) : undefined;
        if (Array.isArray(slice)) {
          dataArray = slice;
        }
      } catch (error) {
        console.error('Failed to strip hidden fields for overview', error);
      }
    }

    const arrayPath = props.fieldPathId.path;
    const labels = await loadOverviewLabels(
      itemUiSchema,
      dataArray,
      arrayPath,
      effectiveTaskId,
      fullFormData
    );
    setOverviewLoading(false);

    const { close } = showDialog({
      children: renderTable(
        items,
        dataArray,
        itemUiSchema,
        props.fieldPathId?.$id ?? 'root',
        arrayPath,
        labels
      ),
      footer: (
        <Bar
          endContent={
            <Button
              onClick={() => {
                close();
              }}>
              Close
            </Button>
          }
        />
      ),
    });
  };

  return (
    <div>
      <label className="form-label px-2 ml-4 -mt-2 bg-white relative float-left z-10">
        {uiOptions.label}
      </label>
      {/* <div className={props.className + " relative border-[2px] border-white border-solid rounded bg-neutral-50 "}> */}
      {/* The above out-commented stuff gives a nice background instead of a border */}
      <div
        className={
          (props.className ?? '') +
          ' relative border-[2px] border-neutral-200 border-solid rounded '
        }>
        {props.items}
        <div className="flex gap-4 m-4 ">
          {props.items.length > 0 ? (
            <Button
              design={ButtonDesign.Transparent}
              disabled={overviewLoading}
              onClick={openOverview}>
              {uiOptions.arrayOverviewButtonText
                ? (uiOptions.arrayOverviewButtonText as string)
                : 'Overview'}
            </Button>
          ) : null}
          {props.canAdd && allowAddRemove && (
            <Button
              design={ButtonDesign.Emphasized}
              onClick={props.onAddClick}
              className="w-[200px]"
              disabled={props.disabled}>
              {uiOptions.arrayAddButtonText ? (uiOptions.arrayAddButtonText as string) : 'Add'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
