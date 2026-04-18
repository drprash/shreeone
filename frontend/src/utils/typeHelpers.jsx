import { TrendingUp, TrendingDown, ArrowRightLeft, DollarSign, PiggyBank, CreditCard, Wallet } from 'lucide-react';

// ---------------------------------------------------------------------------
// Transaction type helpers
// ---------------------------------------------------------------------------

export const getTransactionIcon = (type, size = 'w-5 h-5') => {
  switch (type) {
    case 'INCOME':
      return <TrendingUp className={`${size} text-green-600`} />;
    case 'EXPENSE':
      return <TrendingDown className={`${size} text-red-600`} />;
    case 'TRANSFER':
      return <ArrowRightLeft className={`${size} text-blue-600`} />;
    default:
      return null;
  }
};

export const getTransactionAmountColor = (type) => {
  switch (type) {
    case 'INCOME':
      return 'text-green-600';
    case 'EXPENSE':
      return 'text-red-600';
    case 'TRANSFER':
      return 'text-blue-600';
    default:
      return 'text-gray-900';
  }
};

// ---------------------------------------------------------------------------
// Account type helpers
// ---------------------------------------------------------------------------

export const getAccountIcon = (type, size = 'w-6 h-6') => {
  switch (type) {
    case 'CASH':
      return <DollarSign className={size} />;
    case 'BANK':
      return <PiggyBank className={size} />;
    case 'CREDIT_CARD':
      return <CreditCard className={size} />;
    case 'INVESTMENT':
      return <Wallet className={size} />;
    default:
      return <Wallet className={size} />;
  }
};

// ---------------------------------------------------------------------------
// Country helpers
// ---------------------------------------------------------------------------

const COUNTRY_MAP = {
  AE: { name: 'UAE', flag: '🇦🇪' },
  AU: { name: 'Australia', flag: '🇦🇺' },
  CA: { name: 'Canada', flag: '🇨🇦' },
  CH: { name: 'Switzerland', flag: '🇨🇭' },
  DE: { name: 'Germany', flag: '🇩🇪' },
  FR: { name: 'France', flag: '🇫🇷' },
  GB: { name: 'United Kingdom', flag: '🇬🇧' },
  HK: { name: 'Hong Kong', flag: '🇭🇰' },
  IN: { name: 'India', flag: '🇮🇳' },
  JP: { name: 'Japan', flag: '🇯🇵' },
  MY: { name: 'Malaysia', flag: '🇲🇾' },
  NL: { name: 'Netherlands', flag: '🇳🇱' },
  NZ: { name: 'New Zealand', flag: '🇳🇿' },
  QA: { name: 'Qatar', flag: '🇶🇦' },
  SA: { name: 'Saudi Arabia', flag: '🇸🇦' },
  SG: { name: 'Singapore', flag: '🇸🇬' },
  TH: { name: 'Thailand', flag: '🇹🇭' },
  US: { name: 'United States', flag: '🇺🇸' },
};

export const getCountryDisplay = (code) => {
  if (!code) return null;
  const c = COUNTRY_MAP[code];
  return c ? `${c.flag} ${c.name}` : code;
};

export const getAccountColor = (type) => {
  switch (type) {
    case 'CASH':
      return 'bg-green-100 text-green-600';
    case 'BANK':
      return 'bg-blue-100 text-blue-600';
    case 'CREDIT_CARD':
      return 'bg-red-100 text-red-600';
    case 'INVESTMENT':
      return 'bg-purple-100 text-purple-600';
    default:
      return 'bg-gray-100 text-gray-600';
  }
};
