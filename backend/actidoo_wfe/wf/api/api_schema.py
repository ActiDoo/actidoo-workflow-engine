# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 ActiDoo GmbH


from pydantic import BaseModel, ConfigDict


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_name: str
    correlation_key: str
    data: dict


class SendMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    

#class CallbackRequest(BaseModel):
#    model_config = ConfigDict(from_attributes=True)
#
#    call_token: str # this is the token which has been previously submitted by the called by application
#    callback_token: str|None # this is the new token to reference this workflow
#    task_data: dict
    