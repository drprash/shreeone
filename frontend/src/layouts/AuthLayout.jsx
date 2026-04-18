import { Outlet } from 'react-router-dom';

const AuthLayout = () => {
  return (
    <div className="min-h-screen gradient-bg flex items-center justify-center">
      <div className="glass-panel max-w-md w-full bg-white/80 dark:bg-slate-800/80 rounded-lg shadow-lg p-8">
        <Outlet />
      </div>
    </div>
  );
};

export default AuthLayout;
