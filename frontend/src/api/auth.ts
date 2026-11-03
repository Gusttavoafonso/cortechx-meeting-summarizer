import { request } from './client'
import {
  UserPublic,
  UserLoginRequest,
  UserRegisterRequest,
  GoogleAuthRequest,
} from '../types/auth'

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
