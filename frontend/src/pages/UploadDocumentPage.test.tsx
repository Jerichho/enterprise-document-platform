import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/http";
import { ToastProvider } from "../components/ToastProvider";
import { UploadDocumentPage } from "./UploadDocumentPage";

vi.mock("../api/client", () => ({
  uploadDocument: vi.fn(),
}));

import { uploadDocument } from "../api/client";

const mockedUpload = vi.mocked(uploadDocument);

describe("UploadDocumentPage", () => {
  beforeEach(() => {
    mockedUpload.mockReset();
  });

  it("shows API validation errors from upload failures", async () => {
    const user = userEvent.setup();
    mockedUpload.mockRejectedValue(
      new ApiError("File exceeds the maximum upload size", 400, "file_too_large"),
    );

    const { container } = render(
      <MemoryRouter>
        <ToastProvider>
          <UploadDocumentPage />
        </ToastProvider>
      </MemoryRouter>,
    );

    await user.clear(screen.getByLabelText(/^title$/i));
    await user.type(screen.getByLabelText(/^title$/i), "Handbook");

    const file = new File(["hello"], "handbook.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText(/^file$/i), { target: { files: [file] } });

    const form = container.querySelector("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    expect(mockedUpload).toHaveBeenCalled();
    expect(await screen.findByText(/File exceeds the maximum upload size/i)).toBeInTheDocument();
  });
});
