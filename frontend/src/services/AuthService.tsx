import { getAuthApiUrl } from '@/services/ApiService';
import { deleteAllFormData, openDB } from './DBService';

export function login(): void {
  const apiUrl: string = getAuthApiUrl('do_login', { redirect_url: window.location.href });
  window.location.href = apiUrl;
}

export function logout(): void {
  openDB()
    .then((db) => deleteAllFormData(db))
    .catch((error) => console.error('Error deleting all form data:', error))
    .finally(() => {
      const apiUrl: string = getAuthApiUrl('do_logout', { redirect_url: window.location.href });
      window.location.href = apiUrl;
    });
}