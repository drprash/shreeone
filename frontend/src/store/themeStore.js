import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Helper function to apply theme to DOM
const applyTheme = (theme) => {
  const html = document.documentElement;
  
  if (theme === 'auto') {
    // Check OS preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (prefersDark) {
      html.classList.add('dark');
    } else {
      html.classList.remove('dark');
    }
  } else if (theme === 'dark') {
    html.classList.add('dark');
  } else {
    html.classList.remove('dark');
  }
};

export const useThemeStore = create(
  persist(
    (set, get) => ({
      theme: 'light', // 'light', 'dark', or 'auto'
      isHydrated: false,
      
      setTheme: (newTheme) => {
        set({ theme: newTheme });
        applyTheme(newTheme);
      },
      
      initializeTheme: () => {
        const savedTheme = get().theme;
        applyTheme(savedTheme);
        set({ isHydrated: true });
      },
      
      setIsHydrated: (state) => set({ isHydrated: state }),
    }),
    {
      name: 'shreeone-theme',
      partialize: (state) => ({
        theme: state.theme
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.theme) {
          applyTheme(state.theme);
        }
        state?.setIsHydrated(true);
      }
    }
  )
);

// Listen to OS theme changes when 'auto' is selected
if (typeof window !== 'undefined') {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    const { theme } = useThemeStore.getState();
    if (theme === 'auto') {
      applyTheme('auto');
    }
  });
}
