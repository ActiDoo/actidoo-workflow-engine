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
  datauri?: string | null; //available during adding, not available when showing backend data
  filename?: string | null; //MUST: always available
  hash?: string | null; //not available during adding, available when showing backend data
  id?: string | null; //not available during adding, available when showing backend data
  mimetype?: string | null; //optional: if depictable, it's available during adding and showing backend data
}
const CustomMultiFileField = (props: FieldProps<PcFile[] | null>): ReactElement | null => {
  // console.log("** CustomMultiFileField ********************************************************************************************")
  // console.log(props)

  const { formData: files, onChange } = props;
  const dispatch = useDispatch();
  const onDrop = (event: DragEvent<HTMLDivElement>): void => {
    updateFileList(event.dataTransfer.files);
  };

  const [isDragging, handleDragOver, handleDragLeave, handleDrop] = useDragging(onDrop);
  const [fileUploadKey, setFileUploadKey] = useState<string>('');

  const isDisabled = props.readonly || props.disabled;
  const isRequired = props.schema?.minItems ? true : false

  const label = (props.schema?.title ? props.schema?.title : "File Upload") + (isRequired ? "*" : "")
  const hint = props.uiSchema?.["ui:description"] ? props.uiSchema?.['ui:description'] : "Drag and drop files here or"

  const updateFileList = (fileList: FileList): void => {
    const duplicatedFiles: File[] = [];
    const newFiles: File[] = [];
    const maxFileSize = 15 * 1024 * 1024; // 15MB in bytes
    const oversizedFiles: File[] = [];

    Array.from(fileList).forEach(file => {
      if (file.size > maxFileSize) {
        oversizedFiles.push(file);
      } else if (files?.some(x => x.filename === file.name)) {
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
        const nonNullResults: PcFile[] = results.filter(x => x !== null) as PcFile[];
        onChange([...(files ?? []), ...nonNullResults]);
        setFileUploadKey(getRandomString());
      })
      .catch(() => { });
  };
  const removeFile = (file: PcFile): void => {
    if (files) {
      onChange(_.remove(files, current => current.filename !== file.filename));
    }
  };

  /**
   * In case of a non-required field, we get an empty object {} as formData if there is no file attached. Ok.
   * 
   * In case of a required field, we get an object with an empty list {[]} for formData if there is no file attached:
   * This will look like an attached file without filename etc., which is wrong.
   * Unfortunately this behaviour is implemented in RJSF itself, so as a workaround
   * we delete this invalid file by calling removeFile(), which will result in an undefined formData again.
   */
  if (
    files &&
    files.length == 1 &&
    !(files[0].datauri || files[0].filename || files[0].hash || files[0].id || files[0].mimetype)
  ) {
    console.log(`files undefined: ${props.idSchema.$id}`)
    //remove it async, after rendering, to avoid warnings
    setTimeout(() => {
      removeFile(files[0])
    });
  }


  return (
    <div className="relative">
      <label className="form-label px-2 ml-4 -mt-2 bg-white relative float-left z-10">{label}</label>
      <div className={props.className + " relative border-2 border-neutral-200 border-solid rounded mb-2 p-3"}>
        {!isDisabled && (
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
              <Button className="mt-2 mb-1" design={ButtonDesign.Emphasized}>
                Upload files (15 MB / file)
              </Button>
            </FileUploader>
          </div>
        )}

        {isDisabled && files?.length === 0 && (
          <Text className="bg-neutral-50 w-full p-2 text-center rounded !text-neutral-400">
            No files uploaded
          </Text>
        )}

        {files?.map((file, index) => (
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
