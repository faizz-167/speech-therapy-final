export type UserRole = "therapist" | "patient";

export interface MeResponse {
  user_id: string;
  email: string;
  full_name: string;
  role: UserRole;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
  user_id: string;
  full_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}
