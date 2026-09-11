/**
 * Safely extracts user-readable error messages and metadata from API responses,
 * network errors, timeouts, and validation failures.
 */

export interface ParsedApiError {
  message: string;
  statusCode?: number;
  requestId?: string;
  isNetworkError: boolean;
  isTimeout: boolean;
}

export function parseApiError(err: any, fallback: string = 'An unexpected error occurred.'): ParsedApiError {
  if (!err) {
    return { message: fallback, isNetworkError: false, isTimeout: false };
  }

  if (typeof err === 'string') {
    return { message: err, isNetworkError: false, isTimeout: false };
  }

  const status = err.response?.status;
  const data = err.response?.data;
  const requestId = data?.request_id || err.response?.headers?.['x-request-id'];

  // 1. Timeout detection
  if (err.code === 'ECONNABORTED' || err.message?.toLowerCase().includes('timeout')) {
    return {
      message: 'The request timed out. Please check your internet connection and try again.',
      statusCode: status,
      requestId,
      isNetworkError: false,
      isTimeout: true
    };
  }

  // 2. Network connectivity / server offline detection
  if (err.message === 'Network Error' || !err.response) {
    return {
      message: 'Unable to connect to the server. Please verify your internet connection or server status.',
      statusCode: status,
      requestId,
      isNetworkError: true,
      isTimeout: false
    };
  }

  // 3. Status code-specific messages if no explicit message is in body
  let bodyMessage = '';

  if (data) {
    if (typeof data === 'string') {
      bodyMessage = data;
    } else if (typeof data.message === 'string' && data.message.trim()) {
      bodyMessage = data.message.trim();
    } else if (typeof data.detail === 'string' && data.detail.trim()) {
      bodyMessage = data.detail.trim();
    } else if (Array.isArray(data.detail)) {
      // Pydantic 422 validation error lists: [{ loc, msg, type }]
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

      if (messages.length > 0) {
        bodyMessage = messages.join(', ');
      }
    } else if (typeof data.error === 'string' && data.error.trim()) {
      bodyMessage = data.error.trim();
    }
  }

  if (bodyMessage) {
    return {
      message: requestId ? `${bodyMessage} (Ref: ${requestId})` : bodyMessage,
      statusCode: status,
      requestId,
      isNetworkError: false,
      isTimeout: false
    };
  }

  // Contextual fallback by HTTP Status Code
  switch (status) {
    case 400:
      return { message: 'Invalid request. Please check your input and try again.', statusCode: 400, requestId, isNetworkError: false, isTimeout: false };
    case 401:
      return { message: 'Your session has expired. Please sign in again.', statusCode: 401, requestId, isNetworkError: false, isTimeout: false };
    case 403:
      return { message: 'You do not have permission to perform this action.', statusCode: 403, requestId, isNetworkError: false, isTimeout: false };
    case 404:
      return { message: 'The requested resource was not found.', statusCode: 404, requestId, isNetworkError: false, isTimeout: false };
    case 422:
      return { message: 'The submitted data was incomplete or invalid.', statusCode: 422, requestId, isNetworkError: false, isTimeout: false };
    case 429:
      return { message: 'Too many requests. Please wait a moment before trying again.', statusCode: 429, requestId, isNetworkError: false, isTimeout: false };
    case 500:
    case 502:
    case 503:
    case 504:
      return {
        message: requestId
          ? `A server error occurred. Please try again later. (Error ID: ${requestId})`
          : 'A server error occurred. Please try again later.',
        statusCode: status,
        requestId,
        isNetworkError: false,
        isTimeout: false
      };
    default:
      return {
        message: err.message || fallback,
        statusCode: status,
        requestId,
        isNetworkError: false,
        isTimeout: false
      };
  }
}

export function getErrorMessage(err: any, fallback: string = 'An unexpected error occurred'): string {
  return parseApiError(err, fallback).message;
}
