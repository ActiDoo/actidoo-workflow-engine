import {
  FetchUploadProgressFunc,
  GenericDataActionType,
  GetRequestAdditionalData,
  StringDict,
} from '@/ui5-components';
import { WeDataAction, WeDataKey } from '@/store/generic-data/setup';

export const getRequest = (
  key: WeDataKey,
  additionalData?: GetRequestAdditionalData
): WeDataAction => {
  return {
    type: GenericDataActionType.GET_DATA_REQUEST,
    payload: {
      key,
      params: additionalData?.params,
      queryParams: additionalData?.queryParams,
      keepData: additionalData?.keepData,
    },
  };
};

export const getResponse = (key: WeDataKey, data: any, response: number): WeDataAction => {
  return {
    type: GenericDataActionType.GET_DATA_RESPONSE,
    payload: { key, data, response },
  };
};

export const putRequest = (key: WeDataKey, params: StringDict, body: object): WeDataAction => {
  return {
    type: GenericDataActionType.PUT_DATA_REQUEST,
    payload: { key, params, body },
  };
};

export const putResponse = (key: WeDataKey, response: number): WeDataAction => {
  return {
    type: GenericDataActionType.PUT_DATA_RESPONSE,
    payload: { key, response },
  };
};

export const postRequest = (
  key: WeDataKey,
  body = {},
  params?: StringDict,
  queryParams?: StringDict,
  responseType?: XMLHttpRequestResponseType,
  onUploadProgress?: FetchUploadProgressFunc
): WeDataAction => {
  return {
    type: GenericDataActionType.POST_DATA_REQUEST,
    payload: { key, body, params, queryParams, onUploadProgress },
  };
};

export const postResponse = (key: WeDataKey, response: number, data?: any): WeDataAction => {
  return {
    type: GenericDataActionType.POST_DATA_RESPONSE,
    payload: { key, response, data },
  };
};

export const deleteRequest = (key: WeDataKey, params: StringDict): WeDataAction => {
  return {
    type: GenericDataActionType.DELETE_DATA_REQUEST,
    payload: { key, params },
  };
};

export const deleteResponse = (key: WeDataKey, response: number): WeDataAction => {
  return {
    type: GenericDataActionType.DELETE_DATA_RESPONSE,
    payload: { key, response },
  };
};

export const resetStateForKey = (key: WeDataKey): WeDataAction => {
  return {
    type: GenericDataActionType.RESET_STATE_FOR_KEY,
    payload: { key },
  };
};
