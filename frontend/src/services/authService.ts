/**
 * Service for user authentication and session management.
 */

import { LoginCredentials, AuthResponse, User } from "@/types";
import { mockUsers } from "@/data/mock-documents";

class AuthService {
  private readonly TOKEN_KEY = "glencore_auth_token";
  private readonly USER_KEY = "glencore_user";

  /**
   * Login user
   * TODO: Replace with real API call
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    // Simulate API delay
    await this.simulateDelay(500);

    // Mock implementation
    const user = mockUsers.find(
      u => u.email === credentials.email && u.password === credentials.password
    );

    if (!user) {
      throw new Error("Invalid email or password");
    }

    const token = this.generateMockToken();
    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(); // 24 hours

    const authUser: User = {
      id: user.id,
      name: user.name,
      email: user.email,
      role: user.role,
      department: user.department,
    };

    // Store in localStorage for persistence
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(authUser));

    return {
      user: authUser,
      token,
      expiresAt,
    };

    // Future backend implementation:
    // const response = await fetch('/api/auth/login', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(credentials)
    // });
    // if (!response.ok) throw new Error('Login failed');
    // return await response.json();
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    await this.simulateDelay(200);

    // Clear localStorage
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);

    // Future:
    // await fetch('/api/auth/logout', { method: 'POST' });
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
    await this.simulateDelay(300);

    const newToken = this.generateMockToken();
    localStorage.setItem(this.TOKEN_KEY, newToken);

    return newToken;

    // Future:
    // const response = await fetch('/api/auth/refresh', {
    //   method: 'POST',
    //   headers: { 'Authorization': `Bearer ${this.getToken()}` }
    // });
    // const data = await response.json();
    // return data.token;
  }

  /**
   * Verify token validity
   */
  async verifyToken(): Promise<boolean> {
    await this.simulateDelay(200);

    // Mock: Just check if token exists
    return this.isAuthenticated();

    // Future:
    // const response = await fetch('/api/auth/verify', {
    //   headers: { 'Authorization': `Bearer ${this.getToken()}` }
    // });
    // return response.ok;
  }

  /**
   * Generate mock JWT token (for development only)
   */
  private generateMockToken(): string {
    const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = btoa(JSON.stringify({ 
      sub: "user_id", 
      exp: Date.now() + 24 * 60 * 60 * 1000 
    }));
    const signature = btoa("mock_signature");
    return `${header}.${payload}.${signature}`;
  }

  /**
   * Simulate network delay (for development only)
   */
  private simulateDelay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Export singleton instance
export const authService = new AuthService();
