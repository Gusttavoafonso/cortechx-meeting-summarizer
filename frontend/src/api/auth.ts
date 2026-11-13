import { request } from './client'
import {
  UserPublic,
  UserLoginRequest,
  UserRegisterRequest,
  GoogleAuthRequest,
} from '../types/auth'

export type { UserPublic, UserLoginRequest, UserRegisterRequest, GoogleAuthRequest }

export const authApi = {
  login: (data: UserLoginRequest): Promise<UserPublic> =>
    request<UserPublic>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

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
    request<UserPublic>('/auth/me', {
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
