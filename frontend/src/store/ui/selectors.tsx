import { useSelector } from 'react-redux';
import { State } from '@/store';
import { WeDataKey } from '@/store/generic-data/setup';

export const useSelectUiLoading = (key: WeDataKey, requestType?: 'POST'): boolean | undefined =>
  useSelector((state: State) => state.ui.loading)[`${key}${requestType ?? ''}`];
