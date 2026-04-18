import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      hasPasskey: false,
      passkeyUserId: null,
      isSessionExpired: false,

      setAuth: (data) => {
        set({
          user: data.user,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          isAuthenticated: true,
          isSessionExpired: false,
        });
      },

      clearAuth: () => set({
        user: null,
        accessToken: null,
        refreshToken: null,
        isAuthenticated: false,
        isSessionExpired: false,
      }),

      updateUser: (userData) => set((state) => ({
        user: { ...state.user, ...userData }
      })),

      getAuthHeaders: () => ({
        Authorization: `Bearer ${get().accessToken}`
      }),

      setHasPasskey: (v) => set({ hasPasskey: v }),
      setPasskeyUserId: (id) => set({ passkeyUserId: id }),
      setSessionExpired: (v) => set({ isSessionExpired: v }),
    }),
    {
      name: 'shreeone-auth',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
        hasPasskey: state.hasPasskey,
        passkeyUserId: state.passkeyUserId,
        isSessionExpired: state.isSessionExpired,
      })
    }
  )
);
