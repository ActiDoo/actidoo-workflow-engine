import axios from 'axios';
import { StringDict } from '@/ui5-components';
import { getApiUrl } from '@/services/ApiService';
import { resetStateForKey } from '@/store/generic-data/actions';
import { addToast } from '@/store/ui/actions';
import { WeToastContent } from '@/utils/components/WeToast';
import { WeDataKey } from '@/store/generic-data/setup';
import React, { Dispatch } from 'react';
import { AnyAction } from 'redux';

export const convertBytes = (value: number, digits = 2): string => {
  if (!+value) return '0 Bytes';
  const c = digits < 0 ? 0 : digits;
  const d = Math.floor(Math.log(value) / Math.log(1024));
  return `${parseFloat((value / Math.pow(1024, d)).toFixed(c))} ${
    ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EiB', 'ZB', 'YB'][d]
  }`;
};

export const addNameToDataURL = (dataURL: string | null, name: string): string | null => {
  if (dataURL === null) {
    return null;
  }
  return dataURL ? dataURL.replace(';base64', `;name=${encodeURIComponent(name)};base64`) : dataURL;
};

export const getRandomString = (): string => {
  return Math.random().toString(36);
};

export const loadAndShowFile = async (url: string, data?: StringDict): Promise<boolean> => {
  const genericUrl = getApiUrl(url);
  return await new Promise((resolve, reject) => {
    axios({
      url: genericUrl,
      data,
      responseType: 'blob',
      method: 'post',
      withCredentials: true,
    })
      .then(response => {
        const contentDis = response.request.getResponseHeader('Content-Disposition');
        const url = URL.createObjectURL(response.data);
        const a = document.createElement('a');
        a.href = url;
        a.download = contentDis.split('attachment; filename="')[1].split('"')[0];
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      })
      .catch(e => {
        reject(e);
      })
      .finally(() => {
        resolve(true);
      });
  });
};

export const handleResponse = (
  dispatch: Dispatch<AnyAction>,
  key: WeDataKey,
  response: number | undefined,
  successText?: string,
  errorText?: string,
  onSuccess?: () => void,
  onError?: () => void
): void => {
  if (response === 200) {
    if (successText) dispatch(addToast(<WeToastContent type="success" text={successText} />));
    if (onSuccess) onSuccess();
  } else if (response && response !== 200) {
    if (errorText) dispatch(addToast(<WeToastContent type="error" text={errorText} />));
    if (onError) onError();
  }
  dispatch(resetStateForKey(key));
};
