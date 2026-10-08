// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2025 ActiDoo GmbH

import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { legacy_createStore } from 'redux';

import { I18nProvider } from '@/i18n';
import { PcValueLabelItem } from '@/models/models';
import { useFakeBackend } from '@/test/support/fakeFetchService';
import {
  PropertyOptionsPage,
  UsePropertyOptionsParams,
  usePropertyOptions,
} from '@/rjsf-customs/hooks/usePropertyOptions';

vi.mock('@/ui5-components/services/FetchService', async () =>
  (await import('@/test/support/fakeFetchService')).mockedFetchService()
);

const PARAMS: UsePropertyOptionsParams = {
  taskId: 'task-1',
  propertyPath: ['city'],
  search: '',
  includeValue: undefined,
  formData: {},
};

const opt = (value: string): PcValueLabelItem => ({ value, label: value.toUpperCase() });

// A page of options; with nextOffset the server has more.
const page = (options: PcValueLabelItem[], nextOffset?: number): PropertyOptionsPage => ({
  options,
  has_more: nextOffset !== undefined,
  next_offset: nextOffset ?? null,
});

// Every request waits until the test answers it, in any order.
let requests: Array<{ body: any; answer: (p: PropertyOptionsPage) => Promise<void> }>;

beforeEach(() => {
  requests = [];
  useFakeBackend(
    async call =>
      await new Promise(resolve => {
        requests.push({
          body: call.body,
          answer: async p => {
            await act(async () => {
              resolve({ data: p });
            });
          },
        });
      })
  );
});

const store = legacy_createStore(() => ({}));
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <I18nProvider>
    <Provider store={store}>{children}</Provider>
  </I18nProvider>
);

const renderOptions = () =>
  renderHook((props: UsePropertyOptionsParams) => usePropertyOptions(props), {
    initialProps: PARAMS,
    wrapper,
  });

// Renders the hook and loads a first page "a", "b" that has more.
const renderWithFirstPage = async () => {
  const hook = renderOptions();
  act(() => {
    hook.result.current.reload();
  });
  await waitFor(() => {
    expect(requests).toHaveLength(1);
  });
  await requests[0].answer(page([opt('a'), opt('b')], 2));
  return hook;
};

describe('usePropertyOptions', () => {
  it('loads the first page', async () => {
    const { result } = await renderWithFirstPage();

    expect(requests[0].body).toMatchObject({ property_path: ['city'], search: '', offset: 0 });
    expect(result.current.options).toEqual([opt('a'), opt('b')]);
    expect(result.current.hasMore).toBe(true);
  });

  it('loads the next page on demand and appends it', async () => {
    const { result } = await renderWithFirstPage();

    act(() => {
      result.current.loadMore();
    });
    await waitFor(() => {
      expect(requests).toHaveLength(2);
    });
    await requests[1].answer(page([opt('c')]));

    expect(requests[1].body).toMatchObject({ search: '', offset: 2 });
    expect(result.current.options).toEqual([opt('a'), opt('b'), opt('c')]);
    expect(result.current.hasMore).toBe(false);
  });

  it('drops the answer to an older search', async () => {
    const { result, rerender } = renderOptions();
    act(() => {
      result.current.reload();
    });
    await waitFor(() => {
      expect(requests).toHaveLength(1);
    });

    rerender({ ...PARAMS, search: 'b' });
    act(() => {
      result.current.reload();
    });
    await waitFor(() => {
      expect(requests).toHaveLength(2);
    });
    await requests[1].answer(page([opt('b')]));
    await requests[0].answer(page([opt('a'), opt('b')], 2));

    expect(requests[1].body).toMatchObject({ search: 'b', offset: 0 });
    expect(result.current.options).toEqual([opt('b')]);
    expect(result.current.hasMore).toBe(false);
  });

  it('does not page the old list while a new search waits for its first page', async () => {
    const { result, rerender } = await renderWithFirstPage();
    act(() => {
      result.current.loadMore();
    });
    await waitFor(() => {
      expect(requests).toHaveLength(2);
    });

    // The user types while page 2 of the old search is on its way.
    rerender({ ...PARAMS, search: 'x' });
    act(() => {
      result.current.reload();
    });
    await requests[1].answer(page([opt('c')], 3));
    act(() => {
      result.current.loadMore();
    });

    expect(requests).toHaveLength(2);
    expect(result.current.options).toEqual([opt('a'), opt('b')]);

    await waitFor(() => {
      expect(requests).toHaveLength(3);
    });
    expect(requests[2].body).toMatchObject({ search: 'x', offset: 0 });
  });
});
