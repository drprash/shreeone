export const formatCurrency = (amount, currency = 'USD') => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(amount);
};

export const getCurrencySymbol = (currency = 'USD') => {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })
      .formatToParts(0)
      .find((p) => p.type === 'currency')?.value || currency;
  } catch {
    return currency;
  }
};

export const formatDate = (date) => {
  if (!date) return '';

  if (typeof date === 'string') {
    const datePart = date.split('T')[0];
    const parts = datePart.split('-');

    if (parts.length === 3) {
      const year = Number(parts[0]);
      const month = Number(parts[1]);
      const day = Number(parts[2]);

      if ([year, month, day].every(Number.isFinite)) {
        return new Date(year, month - 1, day).toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric'
        });
      }
    }
  }

  const parsedDate = new Date(date);
  if (Number.isNaN(parsedDate.getTime())) return '';

  return parsedDate.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

export const formatAccountDisplayName = (account) => {
  if (!account) return '';

  const memberFirstName = (account.owner_name || '')
    .trim()
    .split(/\s+/)
    .find(Boolean) || '';

  return memberFirstName ? `${account.name} - ${memberFirstName}` : account.name;
};
