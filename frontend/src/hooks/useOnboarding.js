import { useState, useEffect } from 'react';
import { useAuthStore } from '../store/authStore';

const ADMIN_STEPS = [
  {
    icon: 'home',
    title: 'Welcome, Admin!',
    body: "You control your family's finances here. Let's take a quick tour to get you set up.",
    navHint: null,
  },
  {
    icon: 'layout-dashboard',
    title: 'Your Dashboard',
    body: 'See net worth, spending charts, and per-member breakdowns — all in one place.',
    navHint: { label: 'Dashboard', href: '/' },
  },
  {
    icon: 'wallet',
    title: 'Add Accounts',
    body: 'Start by adding bank accounts, credit cards, loans, or investments for each family member.',
    navHint: { label: 'Accounts', href: '/accounts' },
  },
  {
    icon: 'tags',
    title: 'Customise Categories',
    body: 'Create spending categories that match your family\'s lifestyle — groceries, school fees, EMIs.',
    navHint: { label: 'Categories', href: '/categories' },
  },
  {
    icon: 'settings',
    title: 'Invite Family Members',
    body: 'Add members from Settings and choose a privacy level: Private, Shared, or Family-wide.',
    navHint: { label: 'Settings', href: '/settings' },
  },
  {
    icon: 'target',
    title: 'Set Goals',
    body: 'Create savings targets — a home down-payment, vacation fund, or emergency buffer.',
    navHint: { label: 'Goals', href: '/goals' },
  },
  {
    icon: 'zap',
    title: "You're all set!",
    body: "Use Quick Add on the dashboard to log a transaction in seconds. Your family's finances are in good hands.",
    navHint: null,
  },
];

const MEMBER_STEPS = [
  {
    icon: 'home',
    title: 'Welcome to ShreeOne!',
    body: "Your family's finance hub. Here's a quick look at what you can do.",
    navHint: null,
  },
  {
    icon: 'layout-dashboard',
    title: 'Your Dashboard',
    body: 'See your spending summary, recent transactions, and shared family data at a glance.',
    navHint: { label: 'Dashboard', href: '/' },
  },
  {
    icon: 'zap',
    title: 'Quick Add',
    body: 'The Quick Add panel on the dashboard lets you log an expense or income in just a few taps.',
    navHint: { label: 'Dashboard', href: '/' },
  },
  {
    icon: 'wallet',
    title: 'Your Accounts',
    body: 'View all your linked accounts and current balances in one place.',
    navHint: { label: 'Accounts', href: '/accounts' },
  },
  {
    icon: 'target',
    title: 'Family Goals',
    body: "Track your family's shared savings goals and see how close you are to each target.",
    navHint: { label: 'Goals', href: '/goals' },
  },
];

function tourKey(userId) {
  return `shreeone-tour-${userId}`;
}

export function useOnboarding() {
  const { user, isAuthenticated } = useAuthStore();
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  const steps = user?.role === 'ADMIN' ? ADMIN_STEPS : MEMBER_STEPS;

  useEffect(() => {
    if (!isAuthenticated || !user?.id) return;
    const done = localStorage.getItem(tourKey(user.id));
    if (!done) {
      setCurrentStep(0);
      setIsOpen(true);
    }
  }, [isAuthenticated, user?.id]);

  function markDone() {
    if (user?.id) localStorage.setItem(tourKey(user.id), '1');
    setIsOpen(false);
  }

  function goNext() {
    if (currentStep < steps.length - 1) {
      setCurrentStep((s) => s + 1);
    } else {
      markDone();
    }
  }

  function goPrev() {
    setCurrentStep((s) => Math.max(0, s - 1));
  }

  function skip() {
    markDone();
  }

  return {
    isOpen,
    currentStep,
    steps,
    totalSteps: steps.length,
    step: steps[currentStep],
    goNext,
    goPrev,
    skip,
    isFirst: currentStep === 0,
    isLast: currentStep === steps.length - 1,
  };
}
