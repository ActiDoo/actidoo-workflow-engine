import React, { ReactElement, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom'
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
  ArrayFieldTemplateItemType,
  ArrayFieldTemplateProps,
  FormContextType,
  getTemplate,
  getUiOptions,
  RJSFSchema,
  StrictRJSFSchema,
} from '@rjsf/utils';

export default function CustomArrayFieldTemplate<
  T = any,
  S extends StrictRJSFSchema = RJSFSchema,
  F extends FormContextType = any
>(props: ArrayFieldTemplateProps<T, S, F>): ReactElement | null {

  // console.log("**** Array Field Template ********************************************************************************************")
  // console.log(props)

  const uiOptions = getUiOptions<T, S, F>(props.uiSchema);

  const location = useLocation()

  useEffect(() => {
    // DURING THE FIRST RENDER -> ADD THE MINIMUM ITEMS, WHICH SHALL BE VISIBLE
    
    //check our uischema expectation and only do it on the open tasks page (not later on, when the workflow is completed)
    if (uiOptions && uiOptions["defaultRepetitions"] && location?.pathname?.includes('/tasks/open/')) {

      if (uiOptions["defaultRepetitions"] > 0) {
        // uiOptions["defaultRepetitions"] -> the initial number of displayed items in a dynamic list as the user configured it
        // props.schema.minItems -> the minimum number of items the user has to submit
        // props.items -> the actual display items how RJSF calculated it (unfortunately based on props.schema.minItems)

        // So, it can be that the user does NOT HAVE to submit any item (props.schema.minItems = 0), then RJSF has calculated
        // that no item shall be displayed initially (props.items == empty array), but actually the list
        // is configured to show at least 1 item at the beginning ( uiOptions["defaultRepetitions"]= 1), but which can be
        // deleted by the user, because he does NOT HAVE to submit it.
        // In this case we now insert the missing number of items:

        if (!props.items) //in the tests there was always at least an empty array, but just in case let's catch the non-existence
          props.items = []

        for (let i = 0; i < (uiOptions["defaultRepetitions"] as number - props.items.length); i++) { // add as many items as needed.
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
    }
  }, []);

  //console.log(props.items.length)
  const showDialog = Modals.useShowDialog();
  const items = props.schema.items as unknown as {
    properties: Record<string, { title: string }>;
  };

  const ArrayFieldItemTemplate = getTemplate<'ArrayFieldItemTemplate', T, S, F>(
    'ArrayFieldItemTemplate',
    props.registry,
    uiOptions
  );

  
const renderTable = (items: any, dataArray: any[]): JSX.Element => {
  const tableColumns = items?.properties 
    ? Object.keys(items.properties).map((key, index) => (
        <TableColumn key={`column-${index}`}>
          <Label>{items.properties[key].title}</Label>
        </TableColumn>
      )) 
    : null;

  const isPdfArray = (val: any) => {
    return Array.isArray(val) && val.length > 0 && val.some(item => item.filename && item.filename.includes('.pdf'));
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

//Temporary measure to provide a fallback  if old workflows dont provide the value. 
//Reevaluate its necessity whenever you see this code
  if (typeof uiOptions.arrayAllowAddRemove === 'undefined') {
      uiOptions.arrayAllowAddRemove = "True";
  }

  console.log("Array", String(uiOptions.arrayAllowAddRemove))

  return (
    <div>
      <label className="form-label px-2 ml-4 -mt-2 bg-white relative float-left z-10">{uiOptions["label"]}</label>
      {/* <div className={props.className + " relative border-[2px] border-white border-solid rounded bg-neutral-50 "}> */}
      {/* The above out-commented stuff gives a nice background instead of a border*/}
      <div className={props.className + " relative border-[2px] border-neutral-200 border-solid rounded "}>
        {
        props.items?.map(({ key, ...itemProps }: ArrayFieldTemplateItemType<T, S, F>) => (
          <ArrayFieldItemTemplate key={key} {...itemProps} 
            hasRemove={String(uiOptions.arrayAllowAddRemove) === "True"}
            hasCopy={String(uiOptions.arrayAllowAddRemove) === "True"}
            hasMoveDown={itemProps.hasMoveDown && String(uiOptions.arrayAllowAddRemove) === "True"}
            hasMoveUp={itemProps.hasMoveUp && String(uiOptions.arrayAllowAddRemove) === "True"}
          />
        ))
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
          {props.canAdd && String(uiOptions.arrayAllowAddRemove) === "True" && (
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
