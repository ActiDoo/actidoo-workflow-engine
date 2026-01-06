// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import reducer from '@/store/auth/reducer';
import * as actions from '@/store/auth/actions';
import saga from '@/store/auth/saga';

export default {
  reducer,
  action: actions,
  saga,
};
