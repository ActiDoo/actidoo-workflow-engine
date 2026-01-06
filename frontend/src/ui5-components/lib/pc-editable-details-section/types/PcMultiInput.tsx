// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React, { useEffect, useRef, useState } from 'react';
import {
  Button,
  Input,
  InputDomRef,
  MessageStrip,
  MessageStripDesign,
  Token,
  ValueState,
} from '@ui5/webcomponents-react';

interface PcMultiInputProps {
  values?: string[];
  onChange?: (values: string[]) => void;
  valueState: ValueState;
  valueStateMessage?: string;
  disabled?: boolean;
}
export function PcMultiInput(props: PcMultiInputProps): React.ReactElement {
  const [values, setValues] = useState<string[]>(props.values ?? []);
  const inputEl = useRef<InputDomRef>(null);

  useEffect(() => {
    if (props.onChange) props.onChange(values);
  }, [values]);

  useEffect(() => {
    if (props.values && props.values.length !== 0 && values.length === 0) {
      setValues(v => (props.values ? [...v, ...props.values] : v));
    }
  }, [props.values]);

  return (
    <div>
      {props.valueState === ValueState.Error ? (
        <MessageStrip className="mb-2" design={MessageStripDesign.Negative} hideCloseButton={true}>
          {props.valueStateMessage}
        </MessageStrip>
      ) : null}
      <div className={values.length > 0 ? 'mb-2' : ''}>
        {values.map(a => (
          <Token
            text={a}
            key={a}
            readonly={props.disabled}
            onSelect={() => {
              if (!props.disabled)
                setValues(vals => {
                  return vals.filter(v => v !== a);
                });
            }}></Token>
        ))}
      </div>
      {props.disabled ? null : (
        <>
          <Input ref={inputEl} className="flex-1 mr-2" />
          <Button
            onClick={() => {
              setValues(vals => {
                const v = inputEl.current?.value;
                if (inputEl.current) inputEl.current.value = '';
                return v ? [...vals, v] : vals;
              });
            }}>
            Add item
          </Button>
        </>
      )}
    </div>
  );
}
