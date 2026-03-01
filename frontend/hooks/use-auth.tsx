'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

interface User {
  id: string;
  email: string;
  name?: string;
  full_name?: string;
}

interface UseAuthOptions {
  required?: boolean;
  redirectTo?: string;
}

export function useAuth(options: UseAuthOptions = {}) {
  const { required = false, redirectTo = '/auth/login' } = options;
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const checkAuth = useCallback(async () => {
    const token = api.getToken();

    if (!token) {
      setUser(null);
      setIsAuthenticated(false);
      setLoading(false);
      if (required) {
        router.push(redirectTo);
      }
      return;
    }

    try {
      const userData = await api.getMe();
      setUser(userData);
      setIsAuthenticated(true);
    } catch (error) {
      // Token is invalid or expired
      api.logout();
      setUser(null);
      setIsAuthenticated(false);
      if (required) {
        router.push(redirectTo);
      }
    } finally {
      setLoading(false);
    }
  }, [required, redirectTo, router]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
    setIsAuthenticated(false);
    router.push('/');
  }, [router]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    await checkAuth();
    return response;
  }, [checkAuth]);

  return {
    user,
    loading,
    isAuthenticated,
    logout,
    login,
    checkAuth,
  };
}

// HOC for protected routes
export function withAuth<P extends object>(
  Component: React.ComponentType<P>,
  options: UseAuthOptions = {}
) {
  return function AuthenticatedComponent(props: P) {
    const { loading, isAuthenticated } = useAuth({ required: true, ...options });

    if (loading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      );
    }

    if (!isAuthenticated) {
      return null; // Will redirect via useAuth
    }

    return <Component {...props} />;
  };
}
