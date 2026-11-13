// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it } from 'vitest';

import { WeJsonTree } from '@/utils/components/WeJsonTree';

describe('WeJsonTree', () => {
  it('shows the top level and keeps nested values collapsed', () => {
    const { container } = render(
      <WeJsonTree data={{ name: 'Bodo', amount: 3, empty: null, items: [{ id: 'a' }] }} />
    );

    expect(screen.getByText('"Bodo"')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
    expect(screen.getByText('null')).toBeTruthy();
    expect(screen.getByText('Array(1)')).toBeTruthy();

    const details = container.querySelectorAll('details');
    expect(details).toHaveLength(2);
    details.forEach(node => {
      expect(node.open).toBe(false);
    });
  });
});
