export interface UserPublic {
  id: number
  name: string
  picture_url: string | null
}

export interface UserLoginRequest {
  email: string
  password: string
}

export interface UserRegisterRequest {
  email: string
  password: string
  name: string
}

export interface GoogleAuthRequest {
  credential: string
}

export interface AuthContextType {
  user: UserPublic | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (data: UserLoginRequest) => Promise<UserPublic>
  register: (data: UserRegisterRequest) => Promise<UserPublic>
  loginWithGoogle: (credential: string) => Promise<UserPublic>
  logout: () => Promise<void>
  checkSession: () => Promise<void>
}
