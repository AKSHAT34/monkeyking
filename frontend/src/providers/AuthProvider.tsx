'use client';

import {
  createContext,
  useReducer,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import type { User } from '@/lib/types';
import { authApi } from '@/lib/api/auth';

// ─── State & Actions ────────────────────────────────────
export interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
}

export type AuthAction =
  | { type: 'SET_USER'; payload: { user: User; token: string } }
  | { type: 'LOGOUT' }
  | { type: 'SET_LOADING'; payload: boolean };

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'SET_USER':
      return { user: action.payload.user, token: action.payload.token, loading: false };
    case 'LOGOUT':
      return { user: null, token: null, loading: false };
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
  }
}

// ─── Context ────────────────────────────────────────────
export interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

// ─── Provider ───────────────────────────────────────────
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, {
    user: null,
    token: null,
    loading: true,
  });

  // On mount: validate existing token
  useEffect(() => {
    const token = localStorage.getItem('mk_token');
    if (!token) {
      dispatch({ type: 'SET_LOADING', payload: false });
      return;
    }
    authApi
      .getMe()
      .then((res) => {
        dispatch({ type: 'SET_USER', payload: { user: res.data, token } });
      })
      .catch(() => {
        localStorage.removeItem('mk_token');
        dispatch({ type: 'LOGOUT' });
      });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await authApi.login(email, password);
    localStorage.setItem('mk_token', data.token);
    dispatch({ type: 'SET_USER', payload: { user: data.user, token: data.token } });
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const { data } = await authApi.register(name, email, password);
    localStorage.setItem('mk_token', data.token);
    dispatch({ type: 'SET_USER', payload: { user: data.user, token: data.token } });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('mk_token');
    dispatch({ type: 'LOGOUT' });
    window.location.href = '/mk2026/login';
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
