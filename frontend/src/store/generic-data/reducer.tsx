// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { initState, WeDataAction, WeDataState } from '@/store/generic-data/setup';
import { GenericDataActionType } from '@/ui5-components';
import { postDataResponseReducer } from '@/store/generic-data/reducerPostDataResponse';

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
          data: action.payload.data,
          response: action.payload.response,
        },
      };
    case GenericDataActionType.POST_DATA_REQUEST:
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
    case GenericDataActionType.POST_DATA_RESPONSE:
      return postDataResponseReducer(
        {
          ...state,
          [action.payload.key]: {
            ...state[action.payload.key],
            postResponse: action.payload.response,
            data: action.payload.data,
          },
        },
        action
      );
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
    default:
      return state;
  }
};
