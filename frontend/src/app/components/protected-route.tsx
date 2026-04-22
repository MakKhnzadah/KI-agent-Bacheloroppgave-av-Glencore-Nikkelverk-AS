import type { ReactNode } from "react";
import { Navigate } from "react-router";

import { useAuth } from "@/app/context/auth-context";
import { defaultPathForRole, normalizeUserRole } from "@/utils/role-access";

type ProtectedRouteProps = {
  children: ReactNode;
  allowedRoles?: string[];
};

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { user, isAuthenticated } = useAuth();

  if (!isAuthenticated || !user) {
    return <Navigate to="/" replace />;
  }

  const currentRole = normalizeUserRole(user.role);
  if (allowedRoles && allowedRoles.length > 0 && !allowedRoles.includes(currentRole)) {
    return <Navigate to={defaultPathForRole(currentRole)} replace />;
  }

  return <>{children}</>;
}
