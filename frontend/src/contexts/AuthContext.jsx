import { createContext, useContext, useState, useCallback } from 'react'
import { login as apiLogin } from '../api/auth'
import { getMe } from '../api/users'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('kms_user')) } catch { return null }
  })

  const login = useCallback(async (username, password) => {
    const data = await apiLogin(username, password)
    localStorage.setItem('kms_token', data.access_token)
    const me = await getMe()
    const userData = { username: me.username, role: me.role }
    localStorage.setItem('kms_user', JSON.stringify(userData))
    setUser(userData)
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
