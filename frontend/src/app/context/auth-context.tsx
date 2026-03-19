import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { authService } from "@/services";

interface User {
  name: string;
  initials: string;
  role: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const mapUser = (source: { name: string; role: string; email: string }): User => {
    const initials = source.name
      .split(" ")
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();

    return {
      name: source.name,
      initials,
      role: source.role,
      email: source.email,
    };
  };

  useEffect(() => {
    const existingUser = authService.getCurrentUser();
    if (!existingUser) {
      return;
    }

    setUser(mapUser(existingUser));

    authService.verifyToken().then((isValid) => {
      if (!isValid) {
        setUser(null);
      }
    });
  }, []);

  const login = async (email: string, password: string): Promise<boolean> => {
    if (!email || !password) {
      return false;
    }

    const authResponse = await authService.login({ email, password });
    setUser(mapUser({
      name: authResponse.user.name,
      role: authResponse.user.role,
      email: authResponse.user.email,
    }));
    return true;
  };

  const logout = () => {
    void authService.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}