// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { WeToastContent } from '@/utils/components/WeToast';
import { addNameToDataURL, getRandomString } from '@/services/HelperService';
import { addToast } from '@/store/ui/actions';
import { FieldProps } from '@rjsf/utils';
import { Button, ButtonDesign, FileUploader, Text } from '@ui5/webcomponents-react';
import React, { DragEvent, ReactElement, useState } from 'react';
import { useDispatch } from 'react-redux';
import { MultiFileRow } from '@/rjsf-customs/custom-fields/multiFileField/components/MultiFileRow';
import { useDragging } from '@/utils/hooks/useDragging';
import { isRealFile } from '@/rjsf-customs/custom-fields/multiFileField/attachments';

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

  const isRequired = !!props.required;

  const file = files && isRealFile(files) ? files : undefined;

  const label =
    (props.schema?.title ? props.schema?.title : 'Single File Upload') + (isRequired ? '*' : '');
  const hint = props.uiSchema?.['ui:description']
    ? props.uiSchema?.['ui:description']
    : 'Drag and drop one file here or';

  const updateFileList = (fileList: FileList): void => {
    const maxFileSize = 15 * 1024 * 1024; // 15MB in bytes

    if (fileList.length > 1) {
      dispatch(addToast(<WeToastContent text={`Only one file allowed.`} />));
      return;
    }

    const newFile = fileList[0];

    if (newFile.size > maxFileSize) {
      dispatch(addToast(<WeToastContent text={`File exceeds the max size of 15MB.`} />));
      return;
    } else if (file && file.filename === newFile.name) {
      dispatch(addToast(<WeToastContent text={`File is already in list.`} />));
      return;
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
            resolve(undefined);
          }
        };
        fileReader.readAsDataURL(file);
      });
    };

    processFile(newFile)
      .then(result => {
        onChange(result, fieldPath);
        setFileUploadKey(getRandomString());
      })
      .catch(() => {
        removeFile();
      });
  };

  const removeFile = (): void => {
    onChange(undefined, fieldPath);
  };

  return (
    <div className="relative">
      <label className="form-label px-2 ml-4 -mt-2 bg-white relative float-left z-10">
        {label}
      </label>
      <div
        className={
          (props.className ?? '') +
          ' relative border-2 border-neutral-200 border-solid rounded mb-2 p-3'
        }>
        {!isDisabled && !file && (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={` flex flex-col items-center justify-center text-center ${
              isDragging ? 'border-brand-primary' : 'border-neutral-200'
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

        {isDisabled && !file && (
          <Text className="bg-neutral-50 w-full p-2 text-center rounded !text-neutral-400">
            No files uploaded
          </Text>
        )}

        {file && (
          <MultiFileRow
            key={`file0`}
            file={file}
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
