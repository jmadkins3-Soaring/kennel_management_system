import client from './client'

export const listReservations = (params = {}) =>
  client.get('/reservations', { params }).then(r => r.data)

export const getReservation = id =>
  client.get(`/reservations/${id}`).then(r => r.data)

export const createReservation = body =>
  client.post('/reservations', body).then(r => r.data)

export const updateReservation = (id, body) =>
  client.put(`/reservations/${id}`, body).then(r => r.data)

export const checkinReservation = (id, body) =>
  client.post(`/reservations/${id}/checkin`, body).then(r => r.data)

export const checkoutReservation = (id, body) =>
  client.post(`/reservations/${id}/checkout`, body).then(r => r.data)

export const cancelReservation = (id, body) =>
  client.post(`/reservations/${id}/cancel`, body).then(r => r.data)
