export interface StoredFormData {
  taskId: string; // Unique task identifier
  formData: Record<string, any>; // Dynamic form data
  timestamp: number; // Timestamp of when the data was stored
}

export interface StoredFileData {
  taskId: string; // Unique task identifier
  file: Blob;
  fileName: string;
  fileType: string;
}

export const DB_NAME = 'TaskFormDatabase';
export const DB_VERSION = 1;
export const FORM_STORE = 'forms';

/**
 * Opens the IndexedDB database and creates object stores if they don't exist.
 * @returns {Promise<IDBDatabase>}
 */
export const openDB = async (): Promise<IDBDatabase> => {
  return await new Promise((resolve, reject) => {
    const request: IDBOpenDBRequest = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
      const db: IDBDatabase = (event.target as IDBOpenDBRequest).result;

      // Create 'forms' object store if it doesn't exist
      if (!db.objectStoreNames.contains(FORM_STORE)) {
        db.createObjectStore(FORM_STORE, { keyPath: 'taskId' });
      }
    };

    request.onsuccess = (event: Event) => {
      const db: IDBDatabase = (event.target as IDBOpenDBRequest).result;
      resolve(db);
    };

    request.onerror = (event: Event) => {
      const error = (event.target as IDBOpenDBRequest).error;
      reject(new Error(`Database error: ${error}`));
    };
  });
};

/**
 * Saves dynamic form data to the 'forms' object store for a specific task.
 * @param db - The IndexedDB database instance.
 * @param taskId - The unique identifier for the task.
 * @param data - The dynamic form data to save.
 * @returns {Promise<void>}
 */
export const saveFormData = async (
  db: IDBDatabase,
  taskId: string,
  data: Record<string, any>
): Promise<void> => {
  console.log('saveFormData called');
  const timestamp = Date.now();
  await new Promise((resolve, reject) => {
    const transaction: IDBTransaction = db.transaction([FORM_STORE], 'readwrite');
    const store: IDBObjectStore = transaction.objectStore(FORM_STORE);
    const storedData: StoredFormData = { taskId, formData: data, timestamp };
    const request: IDBRequest<IDBValidKey> = store.put(storedData);

    request.onsuccess = () => {
      resolve(null);
    };

    request.onerror = (event: Event) => {
      const error = (event.target as IDBRequest).error;
      reject(new Error(`Save form data error: ${error}`));
    };
  });
};

/**
 * Retrieves dynamic form data from the 'forms' object store for a specific task.
 * @param db - The IndexedDB database instance.
 * @param taskId - The unique identifier for the task.
 * @returns {Promise<Record<string, any> | null>}
 */
export const getFormData = async (
  db: IDBDatabase,
  taskId: string
): Promise<Record<string, any> | null> => {
  return await new Promise((resolve, reject) => {
    const transaction: IDBTransaction = db.transaction([FORM_STORE], 'readonly');
    const store: IDBObjectStore = transaction.objectStore(FORM_STORE);
    const request: IDBRequest<StoredFormData | undefined> = store.get(taskId);

    request.onsuccess = (event: Event) => {
      const result: StoredFormData | undefined = (
        event.target as IDBRequest<StoredFormData | undefined>
      ).result;
      if (result) {
        resolve(result.formData);
      } else {
        resolve(null);
      }
    };

    request.onerror = (event: Event) => {
      const error = (event.target as IDBRequest).error;
      reject(new Error(`Get form data error: ${error}`));
    };
  });
};

/**
 * Deletes form data from the 'forms' object store for a specific task.
 * @param db - The IndexedDB database instance.
 * @param taskId - The unique identifier for the task.
 * @returns {Promise<void>}
 */
export const deleteFormData = async (db: IDBDatabase, taskId: string): Promise<void> => {
  await new Promise((resolve, reject) => {
    const transaction: IDBTransaction = db.transaction([FORM_STORE], 'readwrite');
    const store: IDBObjectStore = transaction.objectStore(FORM_STORE);
    const request: IDBRequest<undefined> = store.delete(taskId);

    request.onsuccess = () => {
      resolve(null);
    };

    request.onerror = (event: Event) => {
      const error = (event.target as IDBRequest).error;
      reject(new Error(`Delete form data error: ${error}`));
    };
  });
};

/**
 * Deletes form data older than 60 days from the 'forms' object store.
 * @param db - The IndexedDB database instance.
 * @returns {Promise<void>}
 */
export const deleteOldFormData = async (db: IDBDatabase): Promise<void> => {
  const sixtyDaysInMilliseconds = 60 * 24 * 60 * 60 * 1000;
  const now = Date.now();

  await new Promise((resolve, reject) => {
    const transaction: IDBTransaction = db.transaction([FORM_STORE], 'readwrite');
    const store: IDBObjectStore = transaction.objectStore(FORM_STORE);
    const request: IDBRequest<IDBCursorWithValue | null> = store.openCursor();

    request.onsuccess = (event: Event) => {
      const cursor: IDBCursorWithValue | null = (event.target as IDBRequest<IDBCursorWithValue>).result;
      if (cursor) {
        const storedData: StoredFormData = cursor.value;
        if (now - storedData.timestamp > sixtyDaysInMilliseconds) {
          cursor.delete();
        }
        cursor.continue();
      } else {
        resolve(null);
      }
    };

    request.onerror = (event: Event) => {
      const error = (event.target as IDBRequest).error;
      reject(new Error(`Delete old form data error: ${error}`));
    };
  });
};

/**
 * Deletes all form data from the 'forms' object store.
 * @param db - The IndexedDB database instance.
 * @returns {Promise<void>}
 */
export const deleteAllFormData = async (db: IDBDatabase): Promise<void> => {
  await new Promise((resolve, reject) => {
    const transaction: IDBTransaction = db.transaction([FORM_STORE], 'readwrite');
    const store: IDBObjectStore = transaction.objectStore(FORM_STORE);
    const request: IDBRequest<undefined> = store.clear();

    request.onsuccess = () => {
      resolve(null);
    };

    request.onerror = (event: Event) => {
      const error = (event.target as IDBRequest).error;
      reject(new Error(`Delete all form data error: ${error}`));
    };
  });
};