import client from './client'

export const listDogs = (params = {}) =>
  client.get('/dogs', { params }).then(r => r.data)

export const getDog = id =>
  client.get(`/dogs/${id}`).then(r => r.data)

export const createDog = body =>
  client.post('/dogs', body).then(r => r.data)

export const updateDog = (id, body) =>
  client.put(`/dogs/${id}`, body).then(r => r.data)

export const archiveDog = id =>
  client.delete(`/dogs/${id}`)

export const addVaccination = (dogId, body) =>
  client.post(`/dogs/${dogId}/vaccinations`, body).then(r => r.data)

export const updateVaccination = (dogId, index, body) =>
  client.put(`/dogs/${dogId}/vaccinations/${index}`, body).then(r => r.data)
