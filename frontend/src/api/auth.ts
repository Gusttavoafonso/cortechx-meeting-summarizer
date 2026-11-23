import { request } from './client'
import {
  UserPublic,
  UserLoginRequest,
  UserRegisterRequest,
  GoogleAuthRequest,
} from '../types/auth'

export type { UserPublic, UserLoginRequest, UserRegisterRequest, GoogleAuthRequest }

export const authApi = {
  login: (data: UserLoginRequest): Promise<{ access_token: string; token_type: string }> =>
    request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: data.email, password: data.password }),
    }),

  register: (data: UserRegisterRequest): Promise<unknown> =>
    request('/auth/register', {
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
  }),

  logout: (): Promise<{ message: string }> =>
    request<{ message: string }>('/auth/logout', {
      method: 'POST',
    }),
}

export async function getMe(): Promise<UserPublic> {
  return authApi.getMe()
}

export async function loginUser(email: string, password: string): Promise<UserPublic> {
  await authApi.login({ email, password })
  return authApi.getMe()
}

export async function registerUser(
  email: string,
  password: string,
  name: string
): Promise<UserPublic> {
  await authApi.register({ email, password, name })
  await authApi.login({ email, password })
  return authApi.getMe()
}

export async function logoutUser(): Promise<{ message: string }> {
  return authApi.logout()
}
