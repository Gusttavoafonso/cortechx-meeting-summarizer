import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react'
import {
  UserPublic,
  UserLoginRequest,
  UserRegisterRequest,
  AuthContextType,
} from '../types/auth'
import { authApi } from '../api/auth'

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const checkSession = useCallback(async () => {
    try {
      setIsLoading(true)
      const userData = await authApi.getMe()
      setUser(userData)
    } catch {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    checkSession()
  }, [checkSession])

  const login = useCallback(async (data: UserLoginRequest) => {
    const loggedUser = await authApi.login(data)
    setUser(loggedUser)
    return loggedUser
  }, [])

  const register = useCallback(async (data: UserRegisterRequest) => {
    const registeredUser = await authApi.register(data)
    setUser(registeredUser)
    return registeredUser
  }, [])

  const loginWithGoogle = useCallback(async (credential: string) => {
    const googleUser = await authApi.googleAuth({ credential })
    setUser(googleUser)
    return googleUser
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      setUser(null)
    }
  }, [])

  const refreshUser = useCallback(async () => {
    try {
      const userData = await authApi.getMe()
      setUser(userData)
      return userData
    } catch {
      return null
    }
  }, [])

  const updateProfile = useCallback(async (name: string) => {
    const updated = await authApi.updateProfile(name)
    setUser(updated)
    return updated
  }, [])

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      await authApi.changePassword(currentPassword, newPassword)
    },
    []
  )

  const forgotPassword = useCallback(async (email: string) => {
    return authApi.forgotPassword(email)
  }, [])

  const resetPassword = useCallback(async (token: string, newPassword: string) => {
    return authApi.resetPassword(token, newPassword)
  }, [])

  const value: AuthContextType = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    loginWithGoogle,
    logout,
    checkSession,
    updateProfile,
    changePassword,
    forgotPassword,
    resetPassword,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth deve ser utilizado dentro de um AuthProvider')
  }
  return context
}
