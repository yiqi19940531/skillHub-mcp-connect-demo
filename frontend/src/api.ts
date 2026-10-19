export class ApiError extends Error {
  code: string;
  status: number;
  constructor(message: string, code: string, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export function csrf() {
  return (
    document.cookie
      .split("; ")
      .find((value) => value.startsWith("skillhub_csrf="))
      ?.split("=")
      .slice(1)
      .join("=") || ""
  );
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  quietUnauthorized = false,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (init.method && !["GET", "HEAD"].includes(init.method))
    headers.set("X-CSRF-Token", csrf());
  const response = await fetch("/api/v1" + path, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    if (response.status === 401 && path !== "/auth/login" && !quietUnauthorized)
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      result.error?.message || "请求失败，请稍后重试",
      result.error?.code || "REQUEST_FAILED",
      response.status,
    );
  }
  return result.data as T;
}

export function post<T>(path: string, body: unknown) {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
export function patch<T>(path: string, body: unknown) {
  return api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}
export function remove<T>(path: string) {
  return api<T>(path, { method: "DELETE" });
}
