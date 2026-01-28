// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { WeToastContent } from '@/utils/components/WeToast';
import { addNameToDataURL, getRandomString } from '@/services/HelperService';
import { addToast } from '@/store/ui/actions';
import { FieldProps } from '@rjsf/utils';
import { Button, ButtonDesign, FileUploader, Text } from '@ui5/webcomponents-react';
import _ from 'lodash';
import React, { DragEvent, ReactElement, useState } from 'react';
import { useDispatch } from 'react-redux';
import { MultiFileRow } from '@/rjsf-customs/custom-fields/multiFileField/components/MultiFileRow';
import { useDragging } from '@/utils/hooks/useDragging';

export interface PcFile {
  datauri?: string | null;
  filename?: string | null;
  hash?: string | null;
  id?: string | null;
  mimetype?: string | null;
}
const CustomSingleFileField = (props: FieldProps<PcFile | null>): ReactElement | null => {
  // console.log("** CustomSingleFileField ********************************************************************************************")
  const { formData: files, onChange, fieldPathId } = props;
  const fieldPath = fieldPathId?.path ?? [];
  const dispatch = useDispatch();
  const onDrop = (event: DragEvent<HTMLDivElement>): void => {
    updateFileList(event.dataTransfer.files);
  };

  const [isDragging, handleDragOver, handleDragLeave, handleDrop] = useDragging(onDrop);
  const [fileUploadKey, setFileUploadKey] = useState<string>('');

  const isDisabled = !!props.readonly || !!props.disabled;

  const isRequired = props.required ? true : false
  const label = (props.schema?.title ? props.schema?.title : "Single File Upload") + (isRequired ? "*" : "")
  const hint = props.uiSchema?.["ui:description"] ? props.uiSchema?.['ui:description'] : "Drag and drop one file here or"

  const updateFileList = (fileList: FileList): void => {
    const maxFileSize = 15 * 1024 * 1024; // 15MB in bytes

    if (fileList.length > 1) {
      dispatch(
        addToast(
          <WeToastContent text={`Only one file allowed.`} />
        )
      );
      return
    }

    const newFile = fileList[0]

    if (newFile.size > maxFileSize) {
      dispatch(
        addToast(
          <WeToastContent text={`File exceeds the max size of 15MB.`} />
        )
      );
      return
    } else if (files && files.filename === newFile.name) {
      dispatch(
        addToast(
          <WeToastContent text={`File is already in list.`} />
        )
      );
      return
    }

    const processFile = async (file: File) => {
      return await new Promise<PcFile | undefined>(resolve => {
        const fileReader = new FileReader();
        fileReader.onload = e => {
          const result = e.target?.result;
          if (typeof result === 'string') {
            const datauri = addNameToDataURL(result, file.name);
            resolve({
              filename: file.name,
              mimetype: file.type,
              datauri,
            });
          } else {
            resolve(undefined)
          }
        };
        fileReader.readAsDataURL(file);
      });
    }

    processFile(newFile)
    .then(result => {
      onChange(result, fieldPath);
      setFileUploadKey(getRandomString());
    })
    .catch(() => {
      removeFile()
    });
  };

  const removeFile = (): void => {
    onChange(undefined, fieldPath);
  };

  /**
    In case of a non-required field, we initially get "undefined" formData if there is no file attached.
    This is okay, because the schema says that _if_ we have a file it must be an object like this:
    {
      "type": "object",
      "title": "Single upload",
      "properties": {
        "datauri": {
          "type": "string",
          "format": "data-url"git 
        },
        "filename": {
          "type": "string"
        },
        "hash": {
          "type": "string"
        },
        "id": {
          "type": "string"
        },
        "mimetype": {
          "type": "string"
        }
      }

    In case of a required field, we initially get an empty object {} for formData if there is no file attached.
    (Unfortunately this behaviour is implemented in RJSF itself)
    This will look like an attached file without filename etc., which can not be validated due to the above schema,
    (the properties are missing)
    So as a workaround we delete this invalid object by calling removeFile(), which will result in an undefined formData again.
   */
  if (
    files &&
    !(files.datauri || files.filename || files.hash || files.id || files.mimetype)
  ) {
    console.log(`files undefined: ${props.id}`)
    //remove it async, after rendering, to avoid warnings
    setTimeout(() => {
      removeFile()
    });
  }

  return (
    <div className="relative">
      <label className="form-label px-2 ml-4 -mt-2 bg-white relative float-left z-10">{label}</label>
      <div className={props.className + " relative border-2 border-neutral-200 border-solid rounded mb-2 p-3"}>
        {!isDisabled && !files && (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={` flex flex-col items-center justify-center text-center ${isDragging ? 'border-brand-primary' : 'border-neutral-200'
              }`}>
            <Text>{hint}</Text>
            <FileUploader
              key={fileUploadKey}
              multiple
              hideInput
              onChange={e => {
                if (e.detail.files) updateFileList(e.detail.files);
              }}>
              <Button className="mt-2" design={ButtonDesign.Emphasized}>
                Upload file (15 MB / file)
              </Button>
            </FileUploader>
          </div>
        )}

        {isDisabled && !files && (
          <Text className="bg-neutral-50 w-full p-2 text-center rounded !text-neutral-400">
            No files uploaded
          </Text>
        )}

        {files && (
          <MultiFileRow
            key={`file0`}
            file={files}
            disabled={isDisabled}
            onRemove={() => {
              removeFile();
            }}
          />
        )}
      </div>
    </div>
  );
};

export default CustomSingleFileField;
