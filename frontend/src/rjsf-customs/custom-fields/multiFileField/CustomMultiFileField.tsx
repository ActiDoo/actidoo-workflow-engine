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
import { isRealFile } from '@/rjsf-customs/custom-fields/multiFileField/attachments';

export interface PcFile {
  datauri?: string | null; // available during adding, not available when showing backend data
  filename?: string | null; // MUST: always available
  hash?: string | null; // not available during adding, available when showing backend data
  id?: string | null; // not available during adding, available when showing backend data
  mimetype?: string | null; // optional: if depictable, it's available during adding and showing backend data
}
const CustomMultiFileField = (props: FieldProps<PcFile[] | null>): ReactElement | null => {
  // console.log("** CustomMultiFileField ********************************************************************************************")
  // console.log(props)

  const { formData: files, onChange, fieldPathId } = props;
  const fieldPath = fieldPathId?.path ?? [];
  const dispatch = useDispatch();
  const onDrop = (event: DragEvent<HTMLDivElement>): void => {
    updateFileList(event.dataTransfer.files);
  };

  const [isDragging, handleDragOver, handleDragLeave, handleDrop] = useDragging(onDrop);
  const [fileUploadKey, setFileUploadKey] = useState<string>('');

  // eslint-disable-next-line @typescript-eslint/prefer-nullish-coalescing -- logical OR between booleans
  const isDisabled = Boolean(props.readonly || props.disabled);
  const isRequired = !!props.schema?.minItems;

  // Show only real files. Cleaning placeholders out of the data is not this field's
  // job (it happens centrally when the form data is loaded) — rendering must not
  // modify data.
  const visibleFiles = files?.filter(isRealFile);

  const label =
    (props.schema?.title ? props.schema?.title : 'File Upload') + (isRequired ? '*' : '');
  const hint = props.uiSchema?.['ui:description']
    ? props.uiSchema?.['ui:description']
    : 'Drag and drop files here or';

  const updateFileList = (fileList: FileList): void => {
    const duplicatedFiles: File[] = [];
    const newFiles: File[] = [];
    const maxFileSize = 15 * 1024 * 1024; // 15MB in bytes
    const oversizedFiles: File[] = [];

    Array.from(fileList).forEach(file => {
      if (file.size > maxFileSize) {
        oversizedFiles.push(file);
      } else if (visibleFiles?.some(x => x.filename === file.name)) {
        duplicatedFiles.push(file);
      } else {
        newFiles.push(file);
      }
    });

    if (duplicatedFiles.length > 0) {
      dispatch(
        addToast(
          <WeToastContent
            text={`File/s already in list: ${_.map(duplicatedFiles, 'name').join(', ')}`}
          />
        )
      );
    }

    if (oversizedFiles.length > 0) {
      dispatch(
        addToast(
          <WeToastContent
            text={`File/s exceed the max size of 15MB: ${_.map(oversizedFiles, 'name').join(', ')}`}
          />
        )
      );
    }

    Promise.all(
      newFiles.map(async file => {
        return await new Promise<PcFile | null>(resolve => {
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
            }
            resolve(null);
          };
          fileReader.readAsDataURL(file);
        });
      })
    )
      .then(results => {
        const nonNullResults: PcFile[] = results.filter(x => x !== null);
        onChange([...(visibleFiles ?? []), ...nonNullResults], fieldPath);
        setFileUploadKey(getRandomString());
      })
      .catch(() => {});
  };
  const removeFile = (file: PcFile): void => {
    if (visibleFiles) {
      onChange(
        visibleFiles.filter(current => current.filename !== file.filename),
        fieldPath
      );
    }
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
        {!isDisabled && (
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
              <Button className="mt-2 mb-1" design={ButtonDesign.Emphasized}>
                Upload files (15 MB / file)
              </Button>
            </FileUploader>
          </div>
        )}

        {isDisabled && !visibleFiles?.length && (
          <Text className="bg-neutral-50 w-full p-2 text-center rounded !text-neutral-400">
            No files uploaded
          </Text>
        )}

        {visibleFiles?.map((file, index) => (
          <MultiFileRow
            key={`file${index}`}
            file={file}
            disabled={isDisabled}
            onRemove={() => {
              removeFile(file);
            }}
          />
        ))}
      </div>
    </div>
  );
};

export default CustomMultiFileField;
