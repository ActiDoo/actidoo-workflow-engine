import React, { ReactElement } from 'react';
import Form from '@rjsf/core';
import { errorId, FieldErrorProps } from '@rjsf/utils';
import ListGroup from 'react-bootstrap/esm/ListGroup';

const CustomFieldErrorTemplate = (props: FieldErrorProps): ReactElement | null => {
    const { errors = [], idSchema } = props;
    if (errors.length === 0) {
        return null;
    }

    const id = errorId<any>(idSchema);
    let isSingleUpload = false
    let isMultiUpload = false
    if (props.uiSchema && props.uiSchema["ui:field"] && props.uiSchema["ui:field"] == "AttachmentSingle") {
        isSingleUpload = true
    } else if (props.uiSchema && props.uiSchema["ui:field"] && props.uiSchema["ui:field"] == "AttachmentMulti") {
        isMultiUpload = true
    }

    if (isSingleUpload && props.errors && props.errors?.length > 0 && props.errors[0] == "must be object") {
        props.errors[0] = "Bitte einen Anhang anfügen"
    } else if (isMultiUpload && props.errors && props.errors?.length > 0 && props.errors[0] == "must NOT have fewer than 1 items") {
        props.errors[0] = "Bitte mind. einen Anhang anfügen"
    }


    return (
        // copied html from packages/bootstrap-4/src/FieldErrorTemplate/FieldErrorTemplate.tsx:
        <ListGroup as='ul' id={id}>
            {errors.map((error, i) => {
                return (
                    <ListGroup.Item as='li' key={i} className='border-0 m-0 p-0'>
                        <small className='m-0 text-danger'>{error}</small>
                    </ListGroup.Item>
                );
            })}
        </ListGroup>
    );
};


export default CustomFieldErrorTemplate;
