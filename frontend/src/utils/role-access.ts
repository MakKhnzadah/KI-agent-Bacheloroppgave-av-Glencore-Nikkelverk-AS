export function normalizeUserRole(role?: string | null): string {
  const raw = (role || "").trim().toLowerCase();
  if (raw === "reviewer" || raw === "user" || raw === "viewer") {
    return "employee";
  }
  return raw || "employee";
}

export function defaultPathForRole(role?: string | null): string {
  const normalized = normalizeUserRole(role);
  if (normalized === "employee") {
    return "/knowledge-bank";
  }
  return "/dashboard";
}

export function canAccessExpertFeatures(role?: string | null): boolean {
  const normalized = normalizeUserRole(role);
  return normalized === "expert" || normalized === "admin";
}

export function canAccessKnowledgeFeatures(role?: string | null): boolean {
  const normalized = normalizeUserRole(role);
  return normalized === "employee" || normalized === "expert" || normalized === "admin";
}
