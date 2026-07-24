import { Navigate, Route, Routes } from "react-router-dom";

import { AdminRoute, ProtectedRoute } from "../components/ProtectedRoute";
import { AdminPage } from "../pages/AdminPage";
import { AssistantPage } from "../pages/AssistantPage";
import { DocumentDetailPage } from "../pages/DocumentDetailPage";
import { DocumentsPage } from "../pages/DocumentsPage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { StatusPage } from "../pages/StatusPage";
import { UploadDocumentPage } from "../pages/UploadDocumentPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Navigate to="/documents" replace />} />
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/documents/upload" element={<Navigate to="/admin/upload" replace />} />
        <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/status" element={<StatusPage />} />
      </Route>

      <Route element={<AdminRoute />}>
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/upload" element={<UploadDocumentPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/documents" replace />} />
    </Routes>
  );
}
