export const monterreyCenter = [25.6866, -100.3161]

export const restaurants = [
  { id: 'centrito', name: 'Rumbo Kitchen · Centrito', detail: 'Río Orinoco 127, Del Valle', coords: [25.6496, -100.3595] },
  { id: 'tec', name: 'Rumbo Kitchen · Distrito Tec', detail: 'Av. Eugenio Garza Sada', coords: [25.6518, -100.2894] },
  { id: 'jeronimo', name: 'Rumbo Kitchen · San Jerónimo', detail: 'Av. Puerta del Sol', coords: [25.6819, -100.3697] },
]

export const monterreyPlaces = [
  { id: 'centrito-valle', name: 'Centrito Valle', detail: 'San Pedro Garza García', coords: [25.6488, -100.3574] },
  { id: 'campus-tec', name: 'Campus Tec', detail: 'Distrito Tec', coords: [25.6517, -100.2892] },
  { id: 'valle-oriente', name: 'Valle Oriente', detail: 'San Pedro Garza García', coords: [25.6441, -100.3301] },
  { id: 'obispado', name: 'Obispado', detail: 'Monterrey', coords: [25.6786, -100.3428] },
  { id: 'san-jeronimo', name: 'San Jerónimo', detail: 'Monterrey', coords: [25.6834, -100.3690] },
  { id: 'cumbres', name: 'Cumbres', detail: 'Monterrey', coords: [25.7254, -100.3863] },
]

export const menu = [
  {
    id: 'citrus-bowl', name: 'Citrus Bowl', detail: 'Salmón, yuzu y aguacate', price: 198,
    image: 'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=1200&q=85',
  },
  {
    id: 'midnight-ramen', name: 'Midnight Ramen', detail: 'Miso negro, noodles y huevo', price: 176,
    image: 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=1200&q=85',
  },
  {
    id: 'rumbo-box', name: 'Rumbo Box', detail: 'Selección de temporada', price: 224,
    image: 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=85',
  },
]

export const money = (value = 0) => new Intl.NumberFormat('es-MX', {
  style: 'currency', currency: 'MXN', maximumFractionDigits: 0,
}).format(value)

export function displayStatus(status = 'PENDING') {
  return ({ PENDING: 'Buscando courier', MATCHED: 'Courier asignado', IN_TRANSIT: 'En ruta', DELIVERED: 'Entregado' })[status] || status.replaceAll('_', ' ')
}
