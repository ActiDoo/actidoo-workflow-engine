// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 ActiDoo GmbH

import React from 'react';
import { Button, ButtonDesign, ButtonPropTypes } from '@ui5/webcomponents-react';

export interface PcIconButtonProps
  extends Omit<ButtonPropTypes, 'design' | 'tooltip' | 'accessibleName' | 'children'> {
  icon: string;
  /** Shown on hover and used as the accessible name — an icon alone names nothing. */
  tooltip: string;
  /** Destructive actions (delete) only; everything else is the single outlined look. */
  negative?: boolean;
}

/**
 * The one look for icon-only buttons: outlined in the brand color (UI5's
 * "Transparent" design, which this app themes with a brand-colored border),
 * red for destructive actions. Using it everywhere keeps size, hover, focus
 * and the tooltip identical across toolbars, page headers and table rows.
 *
 * UI5's own transparent buttons (table row expander, dialog close) inherit the
 * same border from the theme and are deliberately left alone.
 */
export const PcIconButton: React.FC<PcIconButtonProps> = ({
  icon,
  tooltip,
  negative,
  ...buttonProps
}) => {
  return (
    <Button
      {...buttonProps}
      icon={icon}
      tooltip={tooltip}
      accessibleName={tooltip}
      design={negative ? ButtonDesign.Negative : ButtonDesign.Transparent}
    />
  );
};
