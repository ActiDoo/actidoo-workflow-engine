// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import '@ui5/webcomponents-icons/dist/navigation-right-arrow';

interface PcDateStringProps {
  val?: string;
}
export const PcDateString: React.FC<PcDateStringProps> = props => {
  const dateFormat = props.val ? new Date(props.val).toLocaleString() : '';

  return <>{dateFormat}</>;
};
