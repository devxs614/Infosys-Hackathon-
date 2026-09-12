export const roles = [
  { id: 'client_1', name: 'Cliente 1 (San Pedro)', place: 'Cliente', icon: 'MapPin', user: 'cliente1', pass: '123', route: '/app/client?id=1', tint: 'from-violet/80 to-fuchsia-400/40', description: 'Pedidos y rastreo en tiempo real.' },
  { id: 'client_2', name: 'Cliente 2 (Tec / Valle)', place: 'Cliente', icon: 'Navigation', user: 'cliente2', pass: '123', route: '/app/client?id=2', tint: 'from-cyan/80 to-blue-400/40', description: 'Entrega precisa en Zona Tec.' },
  { id: 'driver', name: 'Rumbo Courier HUD', place: 'Courier', icon: 'Gauge', user: 'driver1', pass: '123', route: '/app/driver', tint: 'from-amber-300/80 to-orange-500/40', description: 'Ruta, batch y acciones de última milla.' },
  { id: 'admin', name: 'Rumbo AI Command Center', place: 'Edge OS', icon: 'Sparkles', user: 'admin', pass: '123', route: '/app/dashboard', tint: 'from-emerald-400/80 to-cyan-400/40', description: 'Métricas y control de eventos en vivo.' },
]

export const clients = {
  '1': {
    id: 'client_1', title: 'Cliente 1 · San Pedro', greeting: 'Tu mesa, a un toque de distancia.',
    locations: [
      { id: 'centrito', name: 'Centrito Valle', detail: 'San Pedro Garza García', coords: [25.65, -100.36] },
      { id: 'san-agustin', name: 'San Agustín', detail: 'Distrito comercial', coords: [25.6528, -100.3376] },
    ],
  },
  '2': {
    id: 'client_2', title: 'Cliente 2 · Tec / Valle', greeting: 'Rumbo encuentra la mejor última milla.',
    locations: [
      { id: 'tec', name: 'Campus Tec', detail: 'Distrito Tec', coords: [25.6517, -100.2892] },
      { id: 'valle', name: 'Valle Oriente', detail: 'Monterrey', coords: [25.6432, -100.3230] },
    ],
  },
}

export const menu = [
  { id: 'citrus-bowl', name: 'Citrus Bowl', detail: 'Salmón, yuzu, aguacate', price: 198, color: '#8b5cf6', shape: 'bowl' },
  { id: 'midnight-ramen', name: 'Midnight Ramen', detail: 'Miso negro, noodles, huevo', price: 176, color: '#06b6d4', shape: 'ramen' },
  { id: 'rumbo-box', name: 'Rumbo Box', detail: 'Selección de temporada', price: 224, color: '#f59e0b', shape: 'box' },
]

export const money = (value = 0) => new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(value)
