import client from './client'

export const listOwners = (params = {}) =>
  client.get('/owners', { params }).then(r => r.data)

export const getOwner = id =>
  client.get(`/owners/${id}`).then(r => r.data)

export const getOwnerDogs = id =>
  client.get(`/owners/${id}/dogs`).then(r => r.data)

export const createOwner = body =>
  client.post('/owners', body).then(r => r.data)

export const updateOwner = (id, body) =>
  client.put(`/owners/${id}`, body).then(r => r.data)

export const archiveOwner = id =>
  client.delete(`/owners/${id}`)
