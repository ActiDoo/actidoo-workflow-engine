import { combineReducers } from 'redux';

import ui from '@/store/ui';
import genericData from '@/store/generic-data';
import authData from '@/store/auth';
import { all } from 'redux-saga/effects';

/***
 * Combination of all reducers
 */

export const rootReducer = combineReducers({
  ui: ui.reducer,
  data: genericData.reducer,
  auth: authData.reducer,
});

export function* rootSaga(): any {
  yield all([genericData.saga(), authData.saga()]);
}

export type State = ReturnType<typeof rootReducer>;
