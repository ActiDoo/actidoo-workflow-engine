// Actions definition for Generic Data
import { FetchUploadProgressFunc, HTTPValidationError, StringDict } from './models';

export interface GenericDataEntry<T> {
  data?: T;
  response?: number;
  queryParams?: StringDict;
  putResponse?: number;
  postResponse?: number;
  deleteResponse?: number;
  validationError?: HTTPValidationError;
}

export enum GenericDataActionType {
  GET_DATA_REQUEST = 'GENERIC_GET_LIST',
  GET_DATA_RESPONSE = 'GENERIC_GET_LIST_RESPONSE',
  POST_DATA_REQUEST = 'GENERIC_POST_DATA_REQUEST',
  POST_DATA_RESPONSE = 'GENERIC_POST_DATA_RESPONSE',
  PUT_DATA_REQUEST = 'GENERIC_PUT_DATA_REQUEST',
  PUT_DATA_RESPONSE = 'GENERIC_PUT_DATA_RESPONSE',
  DELETE_DATA_REQUEST = 'GENERIC_DELETE_DATA_REQUEST',
  DELETE_DATA_RESPONSE = 'GENERIC_DELETE_DATA_RESPONSE',
  RESET_STATE_FOR_KEY = 'RESET_STATE_FOR_KEY',
}

export interface GenericGetRequestAction<K> {
  type: GenericDataActionType.GET_DATA_REQUEST;
  payload: {
    key: K;
    params?: StringDict;
    queryParams?: StringDict;
    keepData?: boolean;
  };
}

export interface GenericGetResponseAction<K, T> {
  type: GenericDataActionType.GET_DATA_RESPONSE;
  payload: {
    key: K;
    data: T | null;
    response: number;
  };
}

export interface GenericPutRequestAction<K> {
  type: GenericDataActionType.PUT_DATA_REQUEST;
  payload: { key: K; params: StringDict; body: object };
}

export interface GenericPutResponseAction<K> {
  type: GenericDataActionType.PUT_DATA_RESPONSE;
  payload: { key: K; response: number; validationError?: HTTPValidationError };
}

export interface GenericPostRequestAction<K> {
  type: GenericDataActionType.POST_DATA_REQUEST;
  payload: {
    key: K;
    body: object;
    params?: StringDict;
    queryParams?: StringDict;
    responseType?: XMLHttpRequestResponseType;
    onUploadProgress?: FetchUploadProgressFunc;
  };
}

export interface GenericPostResponseAction<K, T> {
  type: GenericDataActionType.POST_DATA_RESPONSE;
  payload: { key: K; response: number; validationError?: HTTPValidationError; data?: T | null };
}

export interface GenericDeleteRequestAction<K> {
  type: GenericDataActionType.DELETE_DATA_REQUEST;
  payload: { key: K; params: StringDict };
}

export interface GenericDeleteResponseAction<K> {
  type: GenericDataActionType.DELETE_DATA_RESPONSE;
  payload: { key: K; response: number };
}

export interface GenericResetStateForKeyAction<K> {
  type: GenericDataActionType.RESET_STATE_FOR_KEY;
  payload: {
    key: K;
  };
}

export type GenericDataAction<K, T> =
  | GenericGetRequestAction<K>
  | GenericGetResponseAction<K, T>
  | GenericPutRequestAction<K>
  | GenericPutResponseAction<K>
  | GenericDeleteRequestAction<K>
  | GenericDeleteResponseAction<K>
  | GenericPostRequestAction<K>
  | GenericPostResponseAction<K, T>
  | GenericResetStateForKeyAction<K>;
