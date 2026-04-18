const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

const pad = (value) => String(value).padStart(2, '0');

const dateFromLocalParts = (date) => {
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  return `${year}-${month}-${day}`;
};

export const toNaiveLocalDateTimeString = (value) => {
  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  const seconds = pad(date.getSeconds());

  return `${dateFromLocalParts(date)}T${hours}:${minutes}:${seconds}`;
};

export const toNaiveDateTimeString = (value) => {
  if (typeof value === 'string') {
    const datePart = value.split('T')[0];
    if (DATE_ONLY_PATTERN.test(datePart)) {
      return `${datePart}T00:00:00`;
    }
  }

  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return `${dateFromLocalParts(date)}T00:00:00`;
};

export const formatDateForInput = (value) => {
  if (!value) {
    return '';
  }

  if (typeof value === 'string') {
    const datePart = value.split('T')[0];
    if (DATE_ONLY_PATTERN.test(datePart)) {
      return datePart;
    }
  }

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  return dateFromLocalParts(date);
};

export const parseDateForPicker = (value) => {
  if (!value) {
    return new Date();
  }

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? new Date() : value;
  }

  if (typeof value === 'string') {
    const datePart = value.split('T')[0];
    const parts = datePart.split('-');

    if (parts.length === 3) {
      const year = Number(parts[0]);
      const month = Number(parts[1]);
      const day = Number(parts[2]);

      if ([year, month, day].every(Number.isFinite)) {
        return new Date(year, month - 1, day);
      }
    }
  }

  const parsedDate = new Date(value);
  return Number.isNaN(parsedDate.getTime()) ? new Date() : parsedDate;
};