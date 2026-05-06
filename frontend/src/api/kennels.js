import client from './client'

export const listKennels = (params = {}) =>
  client.get('/kennels', { params }).then(r => r.data)

export const getKennel = id =>
  client.get(`/kennels/${id}`).then(r => r.data)

export const updateKennel = (id, body) =>
  client.put(`/kennels/${id}`, body).then(r => r.data)

export const addHold = (kennelId, body) =>
  client.post(`/kennels/${kennelId}/holds`, body).then(r => r.data)

export const liftHold = (kennelId, holdId) =>
  client.delete(`/kennels/${kennelId}/holds/${holdId}`)

export const getKennelIssues = kennelId =>
  client.get(`/kennels/${kennelId}/issues`).then(r => r.data)
