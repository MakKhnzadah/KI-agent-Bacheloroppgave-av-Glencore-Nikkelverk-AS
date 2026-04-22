/**
 * Service for user authentication and session management.
 */

import { LoginCredentials, AuthResponse, User } from "@/types";
import { normalizeUserRole } from "@/utils/role-access";

export class ServiceError extends Error {
  status: number;
  code?: string;
  details?: Record<string, unknown>;

  constructor(message: string, status: number, code?: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ServiceError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface BackendAuthUser {
  id: string;
  email: string;
  username: string;
  displayName: string;
  role: User["role"];
}

interface BackendLoginResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: "bearer";
  expiresIn: number;
  user: BackendAuthUser;
}

interface BackendRefreshResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: "bearer";
  expiresIn: number;
}

interface BackendVerifyResponse {
  valid: boolean;
  user: BackendAuthUser;
  expiresAt: string;
}

class AuthService {
  private readonly TOKEN_KEY = "glencore_auth_token";
  private readonly REFRESH_TOKEN_KEY = "glencore_refresh_token";
  private readonly USER_KEY = "glencore_user";

  /**
   * Login user
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
      });

      if (!response.ok) {
        throw await this.readServiceError(response, "Login failed");
      }

      const data = (await response.json()) as BackendLoginResponse;
      const authUser = this.mapBackendUser(data.user);
      const expiresAt = new Date(Date.now() + data.expiresIn * 1000).toISOString();

      this.storeSession(authUser, data.accessToken, data.refreshToken);

      return {
        user: authUser,
        token: data.accessToken,
        expiresAt,
      };
    } catch (error) {
      if (error instanceof ServiceError) {
        throw error;
      }

      throw new ServiceError("Unable to reach authentication service", 0, "NETWORK_ERROR");
    }
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    const token = this.getToken();

    try {
      if (token) {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } finally {
      this.clearSession();
    }
  }

  /**
   * Get current user from storage
   */
  getCurrentUser(): User | null {
    const userJson = localStorage.getItem(this.USER_KEY);
    if (!userJson) return null;

    try {
      return JSON.parse(userJson);
    } catch {
      return null;
    }
  }

  /**
   * Get current token from storage
   */
  getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_TOKEN_KEY);
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return this.getToken() !== null && this.getCurrentUser() !== null;
  }

  /**
   * Refresh authentication token
   */
  async refreshToken(): Promise<string> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new ServiceError("No refresh token available", 401, "UNAUTHORIZED");
    }

    const response = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken }),
    });

    if (!response.ok) {
      this.clearSession();
      throw await this.readServiceError(response, "Failed to refresh token");
    }

    const data = (await response.json()) as BackendRefreshResponse;
    localStorage.setItem(this.TOKEN_KEY, data.accessToken);
    localStorage.setItem(this.REFRESH_TOKEN_KEY, data.refreshToken);
    return data.accessToken;
  }

  /**
   * Verify token validity
   */
  async verifyToken(): Promise<boolean> {
    const token = this.getToken();
    if (!token) {
      return false;
    }

    const response = await fetch("/api/auth/verify", {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (response.ok) {
      const data = (await response.json()) as BackendVerifyResponse;
      localStorage.setItem(this.USER_KEY, JSON.stringify(this.mapBackendUser(data.user)));
      return data.valid;
    }

    if (response.status !== 401) {
      return false;
    }

    try {
      const freshToken = await this.refreshToken();
      const retry = await fetch("/api/auth/verify", {
        headers: { Authorization: `Bearer ${freshToken}` },
      });

      if (!retry.ok) {
        return false;
      }

      const data = (await retry.json()) as BackendVerifyResponse;
      localStorage.setItem(this.USER_KEY, JSON.stringify(this.mapBackendUser(data.user)));
      return data.valid;
    } catch {
      return false;
    }
  }

  private mapBackendUser(user: BackendAuthUser): User {
    return {
      id: user.id,
      name: user.displayName,
      email: user.email,
      role: normalizeUserRole(user.role) as User["role"],
    };
  }

  private storeSession(user: User, token: string, refreshToken: string): void {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.REFRESH_TOKEN_KEY, refreshToken);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  }

  private clearSession(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
  }

  private async readServiceError(response: Response, fallbackMessage: string): Promise<ServiceError> {
    try {
      const payload = await response.json();
      const nestedError = payload?.error ?? payload?.detail?.error;
      const message = nestedError?.message ?? fallbackMessage;
      const code = nestedError?.code;
      const details = nestedError?.details;
      return new ServiceError(message, response.status, code, details);
    } catch {
      return new ServiceError(fallbackMessage, response.status);
    }
  }

}

// Export singleton instance
export const authService = new AuthService();
