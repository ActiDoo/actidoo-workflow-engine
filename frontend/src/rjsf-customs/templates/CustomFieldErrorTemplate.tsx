// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import type { ReactElement } from 'react';
import { errorId, FieldErrorProps } from '@rjsf/utils';

const CustomFieldErrorTemplate = (props: FieldErrorProps): ReactElement | null => {
    const { errors = [], fieldPathId, uiSchema } = props;
    if (errors.length === 0) {
        return null;
    }

    const id = errorId(fieldPathId);
    let isSingleUpload = false
    let isMultiUpload = false
    if (uiSchema && uiSchema["ui:field"] && uiSchema["ui:field"] == "AttachmentSingle") {
        isSingleUpload = true
    } else if (uiSchema && uiSchema["ui:field"] && uiSchema["ui:field"] == "AttachmentMulti") {
        isMultiUpload = true
    }

    const normalizedErrors = errors.map((error) => {
        if (typeof error !== 'string') return error;
        if (isSingleUpload && error === "must be object") return "Bitte einen Anhang anfügen";
        if (isMultiUpload && error === "must NOT have fewer than 1 items") return "Bitte mind. einen Anhang anfügen";
        return error;
    });


    return (
        // copied html from packages/bootstrap-4/src/FieldErrorTemplate/FieldErrorTemplate.tsx:
        <ul id={id} className="list-group">
            {normalizedErrors.map((error, i) => (
                <li key={i} className="list-group-item border-0 m-0 p-0">
                    <small className="m-0 text-danger">{error}</small>
                </li>
            ))}
        </ul>
    );
};


export default CustomFieldErrorTemplate;
