const LoadingSpinner = ({ className = 'h-64' }) => (
  <div className={`flex items-center justify-center ${className}`}>
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
  </div>
);

export default LoadingSpinner;
