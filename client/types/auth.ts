export interface User {
  user_id: string;
  email: string;
  full_name: string;
  role: "therapist" | "patient";
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: string;
  full_name: string;
}
