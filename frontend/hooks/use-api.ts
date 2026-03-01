/**
 * React hooks for API interactions with proper loading, error, and caching states.
 *
 * These hooks follow best practices for data fetching in React applications
 * and integrate with the API client for consistent behavior.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { api } from '@/lib/api';

// ==================== Types ====================

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly details: Record<string, unknown>;

  constructor(error: { code: string; message: string; status: number; details?: Record<string, unknown> }) {
    super(error.message);
    this.name = 'ApiClientError';
    this.code = error.code;
    this.status = error.status;
    this.details = error.details || {};
  }

  isUnauthorized(): boolean {
    return this.status === 401;
  }

  isForbidden(): boolean {
    return this.status === 403;
  }

  isNotFound(): boolean {
    return this.status === 404;
  }

  isValidationError(): boolean {
    return this.status === 400 || this.status === 422;
  }

  isServerError(): boolean {
    return this.status >= 500;
  }
}

export interface UseApiState<T> {
  data: T | null;
  error: ApiClientError | null;
  isLoading: boolean;
  isError: boolean;
  isSuccess: boolean;
}

export interface UseApiOptions {
  /** Execute immediately on mount */
  immediate?: boolean;
  /** Callback on success */
  onSuccess?: (data: unknown) => void;
  /** Callback on error */
  onError?: (error: ApiClientError) => void;
}

export interface UseMutationOptions<T, V> {
  /** Callback on success */
  onSuccess?: (data: T, variables: V) => void;
  /** Callback on error */
  onError?: (error: ApiClientError, variables: V) => void;
}

// ==================== Base Hook ====================

/**
 * Generic hook for API calls with loading, error, and success states.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  options: UseApiOptions = {},
): UseApiState<T> & { refetch: () => Promise<T | null> } {
  const { immediate = true, onSuccess, onError } = options;

  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    error: null,
    isLoading: immediate,
    isError: false,
    isSuccess: false,
  });

  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const execute = useCallback(async (): Promise<T | null> => {
    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      isError: false,
    }));

    try {
      const data = await fetcherRef.current();

      if (mountedRef.current) {
        setState({
          data,
          error: null,
          isLoading: false,
          isError: false,
          isSuccess: true,
        });
        onSuccess?.(data);
      }

      return data;
    } catch (error) {
      const apiError = error instanceof ApiClientError
        ? error
        : new ApiClientError({
            code: 'UNKNOWN_ERROR',
            message: error instanceof Error ? error.message : 'Unknown error',
            status: 500,
          });

      if (mountedRef.current) {
        setState({
          data: null,
          error: apiError,
          isLoading: false,
          isError: true,
          isSuccess: false,
        });
        onError?.(apiError);
      }

      return null;
    }
  }, [onSuccess, onError]);

  useEffect(() => {
    mountedRef.current = true;

    if (immediate) {
      execute();
    }

    return () => {
      mountedRef.current = false;
    };
  }, [immediate, execute]);

  return {
    ...state,
    refetch: execute,
  };
}

// ==================== Mutation Hook ====================

/**
 * Hook for POST/PUT/PATCH/DELETE requests with manual trigger.
 */
export function useMutation<T, V = unknown>(
  mutationFn: (variables: V) => Promise<T>,
  options: UseMutationOptions<T, V> = {},
): {
  mutate: (variables: V) => Promise<T | null>;
  mutateAsync: (variables: V) => Promise<T>;
  data: T | null;
  error: ApiClientError | null;
  isLoading: boolean;
  isError: boolean;
  isSuccess: boolean;
  reset: () => void;
} {
  const { onSuccess, onError } = options;

  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    error: null,
    isLoading: false,
    isError: false,
    isSuccess: false,
  });

  const mutateAsync = useCallback(async (variables: V): Promise<T> => {
    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      isError: false,
    }));

    try {
      const data = await mutationFn(variables);

      setState({
        data,
        error: null,
        isLoading: false,
        isError: false,
        isSuccess: true,
      });

      onSuccess?.(data, variables);
      return data;
    } catch (error) {
      const apiError = error instanceof ApiClientError
        ? error
        : new ApiClientError({
            code: 'UNKNOWN_ERROR',
            message: error instanceof Error ? error.message : 'Unknown error',
            status: 500,
          });

      setState({
        data: null,
        error: apiError,
        isLoading: false,
        isError: true,
        isSuccess: false,
      });

      onError?.(apiError, variables);
      throw apiError;
    }
  }, [mutationFn, onSuccess, onError]);

  const mutate = useCallback(async (variables: V): Promise<T | null> => {
    try {
      return await mutateAsync(variables);
    } catch {
      return null;
    }
  }, [mutateAsync]);

  const reset = useCallback(() => {
    setState({
      data: null,
      error: null,
      isLoading: false,
      isError: false,
      isSuccess: false,
    });
  }, []);

  return {
    mutate,
    mutateAsync,
    ...state,
    reset,
  };
}

// ==================== Auth Hook ====================

/**
 * Hook for authentication state and actions.
 */
export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<{
    id: string;
    email: string;
    fullName?: string;
  } | null>(null);

  useEffect(() => {
    const token = api.getToken();
    if (token) {
      api.getMe()
        .then(data => {
          setUser({
            id: data.id,
            email: data.email,
            fullName: data.full_name,
          });
          setIsAuthenticated(true);
        })
        .catch(() => {
          api.logout();
          setIsAuthenticated(false);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);

    const userData = await api.getMe();

    setUser({
      id: userData.id,
      email: userData.email,
      fullName: userData.full_name,
    });
    setIsAuthenticated(true);

    return response;
  }, []);

  const logoutFn = useCallback(() => {
    api.logout();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    return api.register(email, password, fullName);
  }, []);

  return {
    isAuthenticated,
    isLoading,
    user,
    login,
    logout: logoutFn,
    register,
  };
}
