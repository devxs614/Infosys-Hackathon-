export const money = (value = 0) => new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(value)
export const number = (value = 0, digits = 1) => Number(value || 0).toFixed(digits)
export const percent = (value = 0) => `${((value || 0) * 100).toFixed(1)}%`

