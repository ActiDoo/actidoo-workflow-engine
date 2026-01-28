// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { ReactElement, useEffect, useMemo, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom'
import {
  Bar,
  Button,
  ButtonDesign,
  Label,
  Modals,
  Table,
  TableCell,
  TableColumn,
  TableRow,
} from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/duplicate';
import {
  ArrayFieldTemplateProps,
  FormContextType,
  getUiOptions,
  RJSFSchema,
  StrictRJSFSchema,
} from '@rjsf/utils';
import { fetchPost } from '@/ui5-components';
import { getApiUrl } from '@/services/ApiService';
import { PcValueLabelItem } from '@/models/models';
import _ from 'lodash';

export default function CustomArrayFieldTemplate<
  T = any,
  S extends StrictRJSFSchema = RJSFSchema,
  F extends FormContextType = any
>(props: ArrayFieldTemplateProps<T, S, F>): ReactElement | null {

  // console.log("**** Array Field Template ********************************************************************************************")
  // console.log(props)

  const uiOptions = getUiOptions<T, S, F>(props.uiSchema);

  const location = useLocation()
  const { taskId } = useParams();
  const effectiveTaskId = taskId ?? (props.registry as any)?.formContext?.taskId;
  const [dynamicSelectLabels, setDynamicSelectLabels] = useState<Record<string, Record<string, string>>>({});
  const itemUiSchema = (props.uiSchema as any)?.items;
  const itemUiSchemaSignature = JSON.stringify(itemUiSchema ?? null);
  const dynamicSelectConfigs = useMemo<Record<string, any>>(() => {
    if (!itemUiSchema || typeof itemUiSchema !== 'object') {
      return {};
    }

    return Object.entries(itemUiSchema).reduce((acc, [key, config]) => {
      if (
        config &&
        typeof config === 'object' &&
        (config as Record<string, unknown>)['ui:widget'] &&
        ['SelectDynamic', 'MultiSelectDynamic'].includes(
          (config as Record<string, unknown>)['ui:widget'] as string
        )
      ) {
        acc[key] = config;
      }
      return acc;
    }, {} as Record<string, any>);
  }, [itemUiSchemaSignature]);

  useEffect(() => {
    // DURING THE FIRST RENDER -> ADD THE MINIMUM ITEMS, WHICH SHALL BE VISIBLE
    
    //check our uischema expectation and only do it on the open tasks page (not later on, when the workflow is completed)
    const defaultRepetitionsRaw = uiOptions?.["defaultRepetitions"];
    const defaultRepetitions = typeof defaultRepetitionsRaw === 'number' ? defaultRepetitionsRaw : 0;

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
        for (let i = 0; i < (defaultRepetitions - currentItems); i++) { // add as many items as needed.
          // Fake the adding by simulating an ADD click, because ArrayField.tsx from RJSF will take care of it
          // (no need to reimplement the code)
          // I insert a Dummy MouseEvent although an undefined is also handled by the code,
          // but to avoid potential crashes in future RJSF updates when an undefined is no longer accepted.
          // (see onAddClick method in RJSF's ArrayField.tsx)

          setTimeout(() => {
            // With the setTimeout trick we do it asynchronously: otherwise when adding more than 1 item, the next onAddClick() will not be handled properly and no item is added.
            // We also have to have a delay between each inAddClick, therefore each gets 100ms to complete, before the next onAddClick gets executed.
            // (10 ms was not enough, some items were missing but with 100ms we were good, even for adding 10 items in case of the big Workflow)
            props.onAddClick(new MouseEvent("Dummy"))
          }, 100 + i*100)

          //console.log("############# ADD")
        }
    }
  }, []);

  const extractUniqueValues = (dataArray: any[], key: string): string[] => {
    const values = new Set<string>();

    dataArray?.forEach(item => {
      const value = item?.[key];

      if (Array.isArray(value)) {
        value.forEach(v => {
          if (v !== undefined && v !== null) {
            values.add(String(v));
          }
        });
      } else if (value !== undefined && value !== null) {
        values.add(String(value));
      }
    });

    return Array.from(values);
  };

  const formContextSignature = JSON.stringify((props.registry as any)?.formContext?.formData ?? null);
  const dynamicSelectFetchSignature = useMemo(() => {
    const dataArray = Array.isArray(props.formData) ? props.formData : [];
    const fields = Object.entries(dynamicSelectConfigs)
      .map(([fieldKey, fieldUiSchema]) => {
        const propertyPath = (fieldUiSchema as Record<string, any>)['ui:path'];
        const values = extractUniqueValues(dataArray, fieldKey).sort();
        return { fieldKey, propertyPath, values };
      })
      .sort((a, b) => a.fieldKey.localeCompare(b.fieldKey));

    return JSON.stringify({
      taskId: effectiveTaskId ?? null,
      formContextSignature,
      fields,
    });
  }, [dynamicSelectConfigs, effectiveTaskId, formContextSignature, props.formData]);

  useEffect(() => {
    let isActive = true;

    const fetchDynamicLabels = async () => {
      if (!Object.keys(dynamicSelectConfigs).length) {
        setDynamicSelectLabels(prev => (_.isEqual(prev, {}) ? prev : {}));
        return;
      }

      const dataArray = Array.isArray(props.formData) ? props.formData : [];
      const nextLabels: Record<string, Record<string, string>> = {};

      await Promise.all(
        Object.entries(dynamicSelectConfigs).map(async ([fieldKey, fieldUiSchema]) => {
          nextLabels[fieldKey] = {};
          const propertyPath = (fieldUiSchema as Record<string, any>)['ui:path'];
          const values = extractUniqueValues(dataArray, fieldKey);

          if (!effectiveTaskId || !propertyPath || !values.length) {
            return;
          }

          try {
            const response = await fetchPost(getApiUrl('user/search_property_options'), {
              task_id: effectiveTaskId,
              property_path: propertyPath,
              search: '',
              include_value: values.length === 1 ? values[0] : values,
              form_data: (props.registry as any)?.formContext?.formData,
            });

            const options = (response?.data?.options ?? []) as PcValueLabelItem[];

            options.forEach(option => {
              nextLabels[fieldKey][String(option.value)] = `${option.label} (ID: ${option.value})`;
            });
          } catch (error) {
            console.error('Failed to fetch dynamic select labels for overview', error);
          }
        })
      );

      if (isActive) {
        setDynamicSelectLabels(prev => (_.isEqual(prev, nextLabels) ? prev : nextLabels));
      }
    };

    fetchDynamicLabels();

    return () => {
      isActive = false;
    };
  }, [
    dynamicSelectFetchSignature,
    dynamicSelectConfigs,
    effectiveTaskId,
  ]);

  //console.log(props.items.length)
  const showDialog = Modals.useShowDialog();
  const items = props.schema.items as unknown as {
    properties: Record<string, { title: string }>;
  };

  const getDynamicValueLabel = (fieldKey: string, value: unknown): string | null => {
    if (!dynamicSelectConfigs[fieldKey]) {
      return null;
    }

    const mapping = dynamicSelectLabels[fieldKey];
    if (!mapping) {
      return null;
    }

    if (Array.isArray(value)) {
      const labels = value
        .map(v => (v !== undefined && v !== null ? mapping[String(v)] : null))
        .filter((v): v is string => Boolean(v));

      if (!labels.length) {
        return null;
      }

      return labels.join(', ');
    }

    const mapped = mapping[String(value)];
    return mapped || null;
  };

  const renderTable = (items: any, dataArray: any[]): JSX.Element => {
    const tableColumns = items?.properties
      ? Object.keys(items.properties).map((key, index) => (
          <TableColumn key={`column-${index}`}>
            <Label>{items.properties[key].title}</Label>
          </TableColumn>
        ))
      : null;

    const isPdfArray = (val: any) => {
      return (
        Array.isArray(val) &&
        val.length > 0 &&
        val.some(item => item.filename && item.filename.includes('.pdf'))
      );
    };

    const tableRows = dataArray?.map((data, rowIndex) => (
      <TableRow key={`row-${rowIndex}`}>
        {Object.keys(items.properties).map((key) => {
          let val = data[key];

          const property = items.properties[key];
          if (property?.oneOf) {
            const match = property.oneOf.find((o: any) => o.const === val);
            if (match) val = match.title;
          }

          const dynamicLabel = getDynamicValueLabel(key, val);
          if (dynamicLabel) {
            return (
              <TableCell key={`cell-${rowIndex}-${key}`}>
                <Label>{dynamicLabel}</Label>
              </TableCell>
            );
          }

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

          // General check for boolean properties
          if (typeof val === 'boolean') {
            return (
              <TableCell key={`cell-${rowIndex}-${key}`}>
                <Label>{val ? "Yes" : "No"}</Label> {/* Display "Yes" or "No" based on boolean value */}
              </TableCell>
            );
          }

          // Handle nested arrays recursively
          if (property?.type === "array" && Array.isArray(val)) {
            return (
              <TableCell key={`cell-${rowIndex}-${key}`}>
                {renderTable(property.items, val)} 
              </TableCell>
            );
          }

          return (
            <TableCell key={`cell-${rowIndex}-${key}`}>
              <Label>{val}</Label>
            </TableCell>
          );
        })}
      </TableRow>
    ));

    return <Table columns={<>{tableColumns}</>}>{tableRows}</Table>;
  };

  const reviewContent = renderTable(items, props.formData as any[]);

  const allowAddRemove = String((uiOptions as any)?.arrayAllowAddRemove ?? 'True') === 'True';

  return (
    <div>
      <label className="form-label px-2 ml-4 -mt-2 bg-white relative float-left z-10">{uiOptions["label"]}</label>
      {/* <div className={props.className + " relative border-[2px] border-white border-solid rounded bg-neutral-50 "}> */}
      {/* The above out-commented stuff gives a nice background instead of a border*/}
      <div className={props.className + " relative border-[2px] border-neutral-200 border-solid rounded "}>
        {
        props.items
        }
        <div className="flex gap-4 m-4 ">
          {props.items.length > 0 ? (
            <Button
              design={ButtonDesign.Transparent}
              onClick={() => {
                const { close } = showDialog({
                  children: reviewContent,
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
              }}>
              {uiOptions.arrayOverviewButtonText ? (uiOptions.arrayOverviewButtonText as string) : 'Overview'}
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
