import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User, AuthState } from '../types';
import api from '../api/client';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string, fullName: string, orgName?: string) => Promise<boolean>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => {
    return typeof window !== 'undefined' ? localStorage.getItem('locallift_token') : null;
  });
  const [loading, setLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    localStorage.removeItem('locallift_token');
    setToken(null);
    setUser(null);
    setLoading(false);
  }, []);

  // Listen for global 401 session expiration from api client
  useEffect(() => {
    const handleAuthExpired = () => {
      logout();
    };

    window.addEventListener('auth:expired', handleAuthExpired);
    return () => {
      window.removeEventListener('auth:expired', handleAuthExpired);
    };
  }, [logout]);

  useEffect(() => {
    let isMounted = true;

    const fetchMe = async () => {
      const storedToken = localStorage.getItem('locallift_token');
      if (!storedToken) {
        if (isMounted) {
          setUser(null);
          setToken(null);
          setLoading(false);
        }
        return;
      }

      try {
        const resp = await api.get('/auth/me');
        if (isMounted) {
          setUser(resp.data);
          setToken(storedToken);
        }
      } catch (err: any) {
        if (isMounted) {
          localStorage.removeItem('locallift_token');
          setToken(null);
          setUser(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchMe();

    return () => {
      isMounted = false;
    };
  }, [token]);

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);
      const resp = await api.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      const newToken = resp.data.access_token;
      localStorage.setItem('locallift_token', newToken);
      setToken(newToken);
      setUser(resp.data.user);
      return true;
    } catch (e) {
      console.error('Login error:', e);
      return false;
    }
  };

  const register = async (
    email: string,
    password: string,
    fullName: string,
    orgName?: string
  ): Promise<boolean> => {
    try {
      const resp = await api.post('/auth/register', {
        email,
        password,
        full_name: fullName,
        organization_name: orgName || undefined
      });
      const newToken = resp.data.access_token;
      localStorage.setItem('locallift_token', newToken);
      setToken(newToken);
      setUser(resp.data.user);
      return true;
    } catch (e) {
      console.error('Registration error:', e);
      return false;
    }
  };

  const isAuthenticated = Boolean(user && token);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated,
        login,
        register,
        logout,
        loading
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
