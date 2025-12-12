import { ArrayFieldTemplateItemType } from '@rjsf/utils';
import { Button, ButtonDesign } from '@ui5/webcomponents-react';
import React, { ReactElement } from 'react';
import '@ui5/webcomponents-icons/dist/navigation-up-arrow';

const CustomArrayFieldItemTemplate = (props: ArrayFieldTemplateItemType): ReactElement => {
  return (
    <div
      className={` relative m-4  ${props.className} `}>
      <div className="flex gap-2 items-center justify-end">
        <div className="flex-1 ">
          <div className="bg-neutral-100  z-10 text-brand-primary font-fold aspect-square rounded  w-8 h-8 flex items-center justify-center">
            {`${props.index + 1}`}
          </div>
        </div>
        {
          props.hasMoveDown && (
            <Button
              icon="navigation-down-arrow"
              onClick={props.onReorderClick(props.index, props.index + 1)}
              design={ButtonDesign.Transparent}
              disabled={props.disabled}>
            </Button>
          )
        }
        {
          props.hasMoveUp && (
            <Button
              icon="navigation-up-arrow"
              design={ButtonDesign.Transparent}
              onClick={props.onReorderClick(props.index, props.index - 1)}
              disabled={props.disabled}>
            </Button>
          )
        }
        {
          props.hasCopy && (
            <Button
              icon="duplicate"
              design={ButtonDesign.Transparent}
              onClick={props.onCopyIndexClick(props.index)}
              disabled={props.disabled}>
            </Button>
          )
        }
        {
          props.hasRemove && (
            <Button
              icon="delete"
              design={ButtonDesign.Negative}
              onClick={props.onDropIndexClick(props.index)}
              disabled={props.disabled}>
            </Button>
          )
        }
      </div>
      <div className="pt-4 pl-8">{props.children}</div>
    </div>
  );
};
export default CustomArrayFieldItemTemplate;
