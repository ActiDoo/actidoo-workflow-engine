// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { isEqual } from 'lodash';
import { initState, WeDataAction, WeDataState } from '@/store/generic-data/setup';
import { GenericDataActionType } from '@/ui5-components';
import { postDataResponseReducer } from '@/store/generic-data/reducerPostDataResponse';
import { normalizeTaskSchemasForResponse } from '@/store/generic-data/normalizeTaskSchemas';

/**
 * Merge an appended page into the accumulated data: ITEMS concatenated with
 * id-deduplication (page boundaries may shift between fetches), everything else
 * (COUNT, NEXT_CURSOR, ...) taken from the new page.
 */
const mergeItemsPage = (oldData: any, newData: any): any => {
  if (!Array.isArray(oldData?.ITEMS) || !Array.isArray(newData?.ITEMS)) return newData;
  const seen = new Set(oldData.ITEMS.map((item: any) => item?.id));
  return {
    ...newData,
    ITEMS: [...oldData.ITEMS, ...newData.ITEMS.filter((item: any) => !seen.has(item?.id))],
  };
};

export default (state = initState, action: WeDataAction): WeDataState => {
  switch (action.type) {
    case GenericDataActionType.GET_DATA_REQUEST:
      return {
        ...state,
        [action.payload.key]: {
          ...state[action.payload.key],
          data: action.payload.keepData ? state[action.payload.key]?.data : undefined,
          queryParams: action.payload.queryParams,
          response: undefined,
          putResponse: undefined,
          deleteResponse: undefined,
        },
      };
    case GenericDataActionType.GET_DATA_RESPONSE:
      return {
        ...state,
        [action.payload.key]: {
          queryParams: state[action.payload.key]?.queryParams,
          data: normalizeTaskSchemasForResponse(action.payload.key, action.payload.data),
          response: action.payload.response,
        },
      };
    case GenericDataActionType.POST_DATA_REQUEST:
      return {
        ...state,
        [action.payload.key]: {
          ...state[action.payload.key],
          requestSignature: {
            params: action.payload.params,
            queryParams: action.payload.queryParams,
            append: !!action.payload.append,
          },
          response: undefined,
          postResponse: undefined,
          putResponse: undefined,
          deleteResponse: undefined,
        },
      };
    case GenericDataActionType.POST_DATA_RESPONSE: {
      const entry = state[action.payload.key];
      const signature = action.payload.signature;
      // Supersede guard: a response (data OR error) only applies while its echoed
      // signature is still the key's latest request — anything else is stale
      // (newer request or resetStateForKey in between) and is dropped entirely.
      if (signature && !isEqual(entry?.requestSignature, signature)) {
        return state;
      }
      const isAppend = !!signature?.append;
      const succeeded = action.payload.response === 200;
      const normalizedData = normalizeTaskSchemasForResponse(
        action.payload.key,
        action.payload.data
      );
      const data = isAppend
        ? succeeded
          ? mergeItemsPage(entry?.data, normalizedData)
          : entry?.data // failed append: keep the accumulated list untouched
        : normalizedData; // replace: today's behavior (incl. error bodies)
      return postDataResponseReducer(
        {
          ...state,
          [action.payload.key]: {
            ...entry,
            postResponse: action.payload.response,
            data,
            dataSignature: isAppend && !succeeded ? entry?.dataSignature : signature,
          },
        },
        action
      );
    }
    case GenericDataActionType.PUT_DATA_RESPONSE:
      return {
        ...state,
        [action.payload.key]: {
          ...state[action.payload.key],
          putResponse: action.payload.response,
        },
      };
    case GenericDataActionType.DELETE_DATA_RESPONSE:
      return {
        ...state,
        [action.payload.key]: {
          ...state[action.payload.key],
          deleteResponse: action.payload.response,
        },
      };
    case GenericDataActionType.RESET_STATE_FOR_KEY:
      return {
        ...state,
        [action.payload.key]: {
          data: undefined,
          response: undefined,
          postResponse: undefined,
          putResponse: undefined,
          deleteResponse: undefined,
        },
      };
    case GenericDataActionType.CLEAR_RESPONSE_STATUS:
      // Unlike RESET_STATE_FOR_KEY this keeps `data` (and `queryParams`):
      // it only consumes the transient response status fields.
      return {
        ...state,
        [action.payload.key]: {
          ...state[action.payload.key],
          response: undefined,
          postResponse: undefined,
          putResponse: undefined,
          deleteResponse: undefined,
        },
      };
    default:
      return state;
  }
};
