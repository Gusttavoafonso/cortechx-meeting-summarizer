import { request } from './client'
import {
  ForgotPasswordResponse,
  UserPublic,
  UserLoginRequest,
  UserRegisterRequest,
  GoogleAuthRequest,
} from '../types/auth'

export type {
  ForgotPasswordResponse,
  UserPublic,
  UserLoginRequest,
  UserRegisterRequest,
  GoogleAuthRequest,
}

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

  updateProfile: (name: string): Promise<UserPublic> =>
    request<UserPublic>('/users/me', {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),

  changePassword: async (
    currentPassword: string,
    newPassword: string
  ): Promise<void> => {
    await request<void>('/users/me/password', {
      method: 'PUT',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    })
  },

  forgotPassword: (email: string): Promise<ForgotPasswordResponse> =>
    request<ForgotPasswordResponse>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  resetPassword: (
    token: string,
    newPassword: string
  ): Promise<{ message: string }> =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
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
