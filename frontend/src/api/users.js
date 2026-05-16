import client from './client'

export const getMe = () =>
  client.get('/users/me').then(r => r.data)

export const listUsers = () =>
  client.get('/users').then(r => r.data)

export const createUser = body =>
  client.post('/users', body).then(r => r.data)

export const updateUser = (id, body) =>
  client.put(`/users/${id}`, body).then(r => r.data)

export const resetPassword = (id, new_password) =>
  client.post(`/users/${id}/reset-password`, { new_password })
