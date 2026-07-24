import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/http";
import { LoginPage } from "./LoginPage";

const login = vi.fn();

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    user: null,
    token: null,
    loading: false,
    login,
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    login.mockReset();
  });

  it("submits credentials and navigates on success", async () => {
    const user = userEvent.setup();
    login.mockResolvedValue(undefined);
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/documents" element={<p>Documents home</p>} />
        </Routes>
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/email/i), "admin@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(login).toHaveBeenCalledWith("admin@example.com", "password123");
    expect(await screen.findByText("Documents home")).toBeInTheDocument();
  });

  it("shows API error message on failure", async () => {
    const user = userEvent.setup();
    login.mockRejectedValue(new ApiError("Invalid email or password", 401, "invalid_credentials"));
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText(/email/i), "admin@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/Invalid email or password/i)).toBeInTheDocument();
  });
});
