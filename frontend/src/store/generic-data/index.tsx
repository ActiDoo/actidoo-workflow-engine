// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import reducer from '@/store/generic-data/reducer';
import * as actions from '@/store/generic-data/actions';
import saga from '@/store/generic-data/saga';

export default {
  reducer,
  action: actions,
  saga,
};
