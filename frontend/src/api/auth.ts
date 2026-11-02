import { request } from './client'

export interface UserPublic {
  id: number
  email?: string
  name?: string
  picture_url?: string | null
}

export async function getMe(): Promise<UserPublic> {
  return request<UserPublic>('/auth/me', { method: 'GET' })
}

export async function loginUser(
  email: string,
  password: string
): Promise<UserPublic> {
  return request<UserPublic>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function registerUser(
  email: string,
  password: string,
  name: string
): Promise<UserPublic> {
  return request<UserPublic>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  })
}

export async function logoutUser(): Promise<{ message: string }> {
  return request<{ message: string }>('/auth/logout', { method: 'POST' })
}
