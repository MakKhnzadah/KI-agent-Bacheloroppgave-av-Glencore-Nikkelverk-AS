import { beforeEach, describe, expect, it, vi } from "vitest";

import { documentService } from "@/services/documentService";
import { authService, ServiceError } from "@/services/authService";

describe("documentService auth retry", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("retries once after 401 and succeeds with refreshed token", async () => {
    vi.spyOn(authService, "getToken").mockReturnValue("expired-token");
    const refreshSpy = vi.spyOn(authService, "refreshToken").mockResolvedValue("fresh-token");

    const fetchMock = vi.fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Token expired", details: {} } }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "doc-1",
            title: "Doc",
            fileName: "doc.txt",
            category: "Sikkerhet",
            status: "approved",
            uploadedBy: "User",
            uploadedAt: "1. jan 2026 - 10:00",
            originalContent: "orig",
            revisedContent: "rev",
            approvedContent: "rev",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );

    vi.stubGlobal("fetch", fetchMock);

    const result = await documentService.approveDocument("doc-1");

    expect(result.status).toBe("approved");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(refreshSpy).toHaveBeenCalledTimes(1);

    const retryInit = fetchMock.mock.calls[1][1] as RequestInit;
    const retryHeaders = new Headers(retryInit.headers);
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh-token");
  });

  it("throws service error on 403 without refresh", async () => {
    vi.spyOn(authService, "getToken").mockReturnValue("token");
    const refreshSpy = vi.spyOn(authService, "refreshToken").mockResolvedValue("should-not-be-used");

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "FORBIDDEN", message: "Insufficient role", details: {} } }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(documentService.approveDocument("doc-1")).rejects.toMatchObject({
      status: 403,
      code: "FORBIDDEN",
    } as Partial<ServiceError>);

    expect(refreshSpy).not.toHaveBeenCalled();
  });
});
