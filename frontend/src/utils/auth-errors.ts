import { ServiceError } from "@/services/authService";

export function getAuthPermissionErrorMessage(error: unknown): string {
  if (error instanceof ServiceError) {
    if (error.status === 401) {
      return "Sesjonen er utlopt. Logg inn pa nytt og prov igjen.";
    }

    if (error.status === 403) {
      return "Du mangler tilgang til denne handlingen. Kun ekspertbrukere kan utfore dette.";
    }

    if (error.message) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "En uventet feil oppstod. Prov igjen.";
}
