import { describe, expect, it } from "vitest";

import { ServiceError } from "@/services/authService";
import { getAuthPermissionErrorMessage } from "@/utils/auth-errors";

describe("getAuthPermissionErrorMessage", () => {
  it("returns expert-role message for 403 errors", () => {
    const message = getAuthPermissionErrorMessage(
      new ServiceError("Insufficient role", 403, "FORBIDDEN"),
    );

    expect(message).toContain("Kun ekspertbrukere");
  });
});
