/**
 * Safely extracts a user-readable error message string from any Axios error,
 * Pydantic 422 error object/array, or standard Error.
 */
export function getErrorMessage(err: any, fallback: string = 'An unexpected error occurred'): string {
  if (!err) return fallback;
  if (typeof err === 'string') return err;

  const data = err.response?.data;
  if (data) {
    if (typeof data === 'string') return data;
    if (typeof data.message === 'string' && data.message.trim()) return data.message;
    if (typeof data.detail === 'string' && data.detail.trim()) return data.detail;

    // Handle Pydantic 422 validation error arrays: [{ loc, msg, type, input }]
    if (Array.isArray(data.detail)) {
      const messages = data.detail
        .map((item: any) => {
          if (typeof item === 'string') return item;
          if (item?.msg) {
            const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : '';
            return field && field !== 'body' ? `${field}: ${item.msg}` : item.msg;
          }
          return typeof item === 'object' ? JSON.stringify(item) : String(item);
        })
        .filter(Boolean);

      if (messages.length > 0) return messages.join(', ');
    }

    if (typeof data.error === 'string' && data.error.trim()) return data.error;
  }

  if (typeof err.message === 'string' && err.message.trim()) {
    return err.message;
  }

  return fallback;
}
