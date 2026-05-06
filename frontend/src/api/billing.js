import client from './client'

export const listBills = (params = {}) =>
  client.get('/bills', { params }).then(r => r.data)

export const getBill = id =>
  client.get(`/bills/${id}`).then(r => r.data)

export const markPaid = id =>
  client.post(`/bills/${id}/pay`).then(r => r.data)
