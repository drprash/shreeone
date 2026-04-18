import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Home,
  LayoutDashboard,
  Wallet,
  Tags,
  Settings,
  Target,
  Zap,
  ArrowRight,
  ArrowLeft,
  X,
} from 'lucide-react';
import { useOnboarding } from '../../hooks/useOnboarding';

const ICON_MAP = {
  home: Home,
  'layout-dashboard': LayoutDashboard,
  wallet: Wallet,
  tags: Tags,
  settings: Settings,
  target: Target,
  zap: Zap,
};

const OnboardingTour = () => {
  const navigate = useNavigate();
  const { isOpen, currentStep, totalSteps, step, goNext, goPrev, skip, isFirst, isLast } =
    useOnboarding();

  // Navigate to the page shown in the background when the step changes
  useEffect(() => {
    if (isOpen && step?.navHint) {
      navigate(step.navHint.href);
    }
  }, [isOpen, currentStep]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isOpen || !step) return null;

  const StepIcon = ICON_MAP[step.icon] ?? Home;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4"
      role="dialog"
      aria-modal="true"
      aria-label="Onboarding tour"
    >
      <div className="relative bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-md p-8 flex flex-col gap-6">
        {/* Skip */}
        <button
          type="button"
          onClick={skip}
          aria-label="Skip tour"
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Icon */}
        <div className="flex justify-center">
          <div className="bg-blue-50 dark:bg-blue-900/40 rounded-2xl p-5">
            <StepIcon className="w-10 h-10 text-blue-600 dark:text-blue-400" />
          </div>
        </div>

        {/* Text */}
        <div className="text-center space-y-2">
          <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-100">
            {step.title}
          </h2>
          <p className="text-slate-500 dark:text-slate-400 text-sm leading-relaxed">
            {step.body}
          </p>
          {step.navHint && (
            <p className="text-xs text-blue-500 dark:text-blue-400 font-medium mt-1">
              Showing: {step.navHint.label}
            </p>
          )}
        </div>

        {/* Step dots */}
        <div className="flex justify-center gap-1.5">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              className={`rounded-full transition-all duration-200 ${
                i === currentStep
                  ? 'w-5 h-2 bg-blue-600 dark:bg-blue-400'
                  : 'w-2 h-2 bg-slate-200 dark:bg-slate-600'
              }`}
            />
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={goPrev}
            disabled={isFirst}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-0 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>

          <button
            type="button"
            onClick={goNext}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors"
          >
            {isLast ? (
              'Get started'
            ) : (
              <>
                Next
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>

        <p className="text-center text-xs text-slate-400 dark:text-slate-500">
          {currentStep + 1} of {totalSteps}
        </p>
      </div>
    </div>
  );
};

export default OnboardingTour;
