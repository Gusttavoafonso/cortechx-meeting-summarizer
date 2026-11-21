import { request } from './client'
import {
  UserPublic,
  UserLoginRequest,
  UserRegisterRequest,
  GoogleAuthRequest,
} from '../types/auth'

export type { UserPublic, UserLoginRequest, UserRegisterRequest, GoogleAuthRequest }

export const authApi = {
  login: async (data: UserLoginRequest): Promise<UserPublic> => {
    await request<{ access_token: string; token_type: string }>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: data.email, password: data.password }),
      credentials: 'include',
    })
    return authApi.getMe()
  },

  register: (data: UserRegisterRequest): Promise<UserPublic> =>
    request<UserPublic>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  googleAuth: (data: GoogleAuthRequest): Promise<UserPublic> =>
    request<UserPublic>('/auth/google', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getMe: (): Promise<UserPublic> =>
    request<UserPublic>('/users/me', {
      method: 'GET',
      credentials: 'include',
    }),

  logout: (): Promise<{ message: string }> =>
    request<{ message: string }>('/auth/logout', {
      method: 'POST',
    }),
}

export async function getMe(): Promise<UserPublic> {
  return authApi.getMe()
}

export async function loginUser(
  email: string,
  password: string
): Promise<UserPublic> {
  return authApi.login({ email, password })
}

export async function registerUser(
  email: string,
  password: string,
  name: string
): Promise<UserPublic> {
  return authApi.register({ email, password, name })
}

export async function logoutUser(): Promise<{ message: string }> {
  return authApi.logout()
}
