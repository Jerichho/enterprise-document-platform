import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { uploadDocument } from "../api/client";
import { ApiError } from "../api/http";
import { ErrorBanner } from "../components/ErrorBanner";
import { useToast } from "../components/ToastProvider";

export function UploadDocumentPage() {
  const navigate = useNavigate();
  const { pushToast } = useToast();
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("HR");
  const [category, setCategory] = useState("Policy");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF, DOCX, or TXT file");
      return;
    }
    setSubmitting(true);
    setError(null);
    setProgress(0);
    try {
      const document = await uploadDocument({
        file,
        title,
        department,
        category,
        onProgress: setProgress,
      });
      setProgress(100);
      pushToast(`Uploaded “${document.title}”. Ingestion started.`, "ok");
      navigate(`/documents/${document.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <h2>Upload document</h2>
      <p className="muted">
        Admins can upload PDF, DOCX, or TXT files. Ingestion runs in the background after upload.
      </p>
      <form className="stack-form" onSubmit={onSubmit}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required disabled={submitting} />
        </label>
        <label>
          Department
          <input
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            required
            disabled={submitting}
          />
        </label>
        <label>
          Category
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            required
            disabled={submitting}
          />
        </label>
        <label>
          File
          <input
            type="file"
            accept=".pdf,.docx,.txt,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
            disabled={submitting}
          />
        </label>

        {submitting && (
          <div className="upload-progress" aria-live="polite">
            <div className="upload-progress-bar" style={{ width: `${progress}%` }} />
            <p className="muted">Uploading… {progress}%</p>
          </div>
        )}

        {error && <ErrorBanner message={error} />}
        <div className="button-row">
          <button className="btn primary" type="submit" disabled={submitting}>
            {submitting ? "Uploading…" : "Upload & ingest"}
          </button>
          <Link className="btn ghost" to="/documents">
            Cancel
          </Link>
        </div>
      </form>
    </section>
  );
}
