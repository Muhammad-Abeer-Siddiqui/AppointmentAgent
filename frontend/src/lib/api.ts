const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type FetchOptions = {
  method?: string;
  body?: any;
  headers?: Record<string, string>;
  token?: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T = any>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { method = "GET", body, token } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail || "Request failed");
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

// Auth API
export const authApi = {
  register: (data: { email: string; password: string; name: string }) =>
    apiFetch("/auth/register", { method: "POST", body: data }),

  login: (data: { email: string; password: string }) =>
    apiFetch("/auth/login", { method: "POST", body: data }),

  logout: (token: string) =>
    apiFetch("/auth/logout", { method: "POST", token }),

  googleLogin: (token: string) =>
    apiFetch("/auth/google/login", { token }),
};

// User API
export const userApi = {
  getMe: (token: string) => apiFetch("/users/me", { token }),

  updateMe: (token: string, data: { name?: string; timezone?: string }) =>
    apiFetch("/users/me", { method: "PATCH", body: data, token }),
};

// Calendar API
export const calendarApi = {
  getAppointments: (token: string, params?: { start_date?: string; end_date?: string }) => {
    const query = params
      ? "?" + new URLSearchParams(params as any).toString()
      : "";
    return apiFetch(`/calendar${query}`, { token });
  },

  deleteAppointment: (token: string, appointmentId: number) =>
    apiFetch(`/appointments/${appointmentId}`, { method: "DELETE", token }),
};

// Agent API
export const agentApi = {
  chat: (
    token: string,
    data: {
      message: string;
      conversation_history?: Array<{ role: string; content: string }>;
    },
  ) => apiFetch("/agent/chat", { method: "POST", body: data, token }),

  searchAvailability: (
    token: string,
    data: {
      duration_minutes: number;
      start_date: string;
      end_date: string;
      user_tz: string;
    },
  ) => apiFetch("/agent/search-availability", { method: "POST", body: data, token }),

  createAppointment: (
    token: string,
    data: {
      title: string;
      description?: string;
      start_time: string;
      end_time: string;
      duration_minutes: number;
    },
  ) => apiFetch("/agent/create-appointment", { method: "POST", body: data, token }),
};
