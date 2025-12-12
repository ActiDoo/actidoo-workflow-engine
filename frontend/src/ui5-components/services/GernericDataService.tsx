import { FetchMethods } from '../models/models';
import { GenericDataEntry } from '../models/generic-data-models';

export const handleStateResponse = (
  state: GenericDataEntry<any> | null
): { e: boolean; toastText: string | undefined; navigateBack: boolean } => {
  let navigateBack = false;
  let e = false;
  let toastText;
  if (state?.deleteResponse === 200) {
    navigateBack = true;
    toastText = 'Deleting was successful';
  } else if (state?.deleteResponse) {
    e = true;
  }
  if (state?.putResponse === 200) {
    toastText = 'Saving was successful';
  } else if (state?.putResponse) {
    e = true;
  }
  if (state?.postResponse === 200) {
    navigateBack = true;
    toastText = 'Creating was successful';
  } else if (state?.postResponse) {
    e = true;
  }
  return { e, toastText, navigateBack };
};

export const isGenericDataLoading = (
  dataKey: string,
  loading: Record<string, boolean>
): boolean => {
  return (
    loading[dataKey] ||
    loading[`${dataKey}${FetchMethods.POST}`] ||
    loading[`${dataKey}${FetchMethods.PUT}`] ||
    loading[`${dataKey}${FetchMethods.DELETE}`]
  );
};
