import { createContext, useContext, useState, useCallback } from 'react'
import { login as apiLogin } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('kms_user')) } catch { return null }
  })

  const login = useCallback(async (username, password) => {
    const data = await apiLogin(username, password)
    localStorage.setItem('kms_token', data.access_token)
    localStorage.setItem('kms_user', JSON.stringify({ username }))
    setUser({ username })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('kms_token')
    localStorage.removeItem('kms_user')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
