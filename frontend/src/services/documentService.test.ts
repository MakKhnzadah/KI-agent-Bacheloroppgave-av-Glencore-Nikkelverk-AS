import { beforeEach, describe, expect, it, vi } from "vitest";

import { documentService } from "@/services/documentService";
import { authService } from "@/services/authService";
import { ApiError } from "@/services/apiClient";

describe("documentService error handling", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("retries once after 401 and succeeds with refreshed token", async () => {
    vi.spyOn(authService, "getToken").mockReturnValueOnce("expired-token").mockReturnValue("fresh-token");
    const refreshSpy = vi.spyOn(authService, "refreshToken").mockResolvedValue("fresh-token");

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Token expired", details: {} } }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "approved" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "applied" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            suggestion_id: "doc-1",
            upload_id: "upl-1",
            status: "applied",
            suggestion_json: "---\ntitle: \"Doc\"\ncategory: \"Sikkerhet\"\n---\n\nInnhold",
            created_at: "2026-03-22 12:00:00",
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );

    vi.stubGlobal("fetch", fetchMock);

    const result = await documentService.approveDocument("doc-1");

    expect(result.id).toBe("doc-1");
    expect(result.status).toBe("approved");
    expect(refreshSpy).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(4);

    const firstHeaders = new Headers((fetchMock.mock.calls[0][1] as RequestInit).headers);
    const retryHeaders = new Headers((fetchMock.mock.calls[1][1] as RequestInit).headers);
    expect(firstHeaders.get("Authorization")).toBe("Bearer expired-token");
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh-token");
  });

  it("throws api error on 403 without refresh", async () => {
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
    } as Partial<ApiError>);

    expect(refreshSpy).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
