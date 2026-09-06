import React, { createContext, useContext, useState, useEffect } from 'react';
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
  const [token, setToken] = useState<string | null>(localStorage.getItem('locallift_token'));
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchMe = async () => {
      if (!token) {
        setUser(null);
        setLoading(false);
        return;
      }

      try {
        const resp = await api.get('/auth/me');
        setUser(resp.data);
      } catch (err) {
        console.error('Failed to restore session:', err);
        localStorage.removeItem('locallift_token');
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    fetchMe();
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

  const logout = () => {
    localStorage.removeItem('locallift_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated: !!user, login, register, logout, loading }}>
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
