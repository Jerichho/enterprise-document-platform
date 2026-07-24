import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AdminRoute, ProtectedRoute } from "../components/ProtectedRoute";

vi.mock("../hooks/useAuth", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "../hooks/useAuth";

const mockedUseAuth = vi.mocked(useAuth);

describe("ProtectedRoute", () => {
  it("redirects unauthenticated users to login", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      token: null,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/documents"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/documents" element={<p>Secret docs</p>} />
          </Route>
          <Route path="/login" element={<p>Login gate</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Login gate")).toBeInTheDocument();
    expect(screen.queryByText("Secret docs")).not.toBeInTheDocument();
  });

  it("renders outlet for authenticated users", () => {
    mockedUseAuth.mockReturnValue({
      user: {
        id: "1",
        email: "e@example.com",
        full_name: "Employee",
        role: "employee",
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      token: "tok",
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/documents"]}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/documents" element={<p>Secret docs</p>} />
          </Route>
          <Route path="/login" element={<p>Login gate</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Secret docs")).toBeInTheDocument();
  });
});

describe("AdminRoute", () => {
  it("redirects employees away from admin routes", () => {
    mockedUseAuth.mockReturnValue({
      user: {
        id: "1",
        email: "e@example.com",
        full_name: "Employee",
        role: "employee",
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      token: "tok",
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<p>Admin panel</p>} />
          </Route>
          <Route path="/documents" element={<p>Documents home</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Documents home")).toBeInTheDocument();
    expect(screen.queryByText("Admin panel")).not.toBeInTheDocument();
  });
});
