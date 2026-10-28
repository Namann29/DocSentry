import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./auth";
import Layout from "./components/Layout";
import { ToastProvider } from "./components/ui";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Investigate from "./pages/Investigate";
import Scan from "./pages/Scan";
import Compare from "./pages/Compare";
import Overview from "./pages/Overview";
import Cases from "./pages/Cases";
import CreateCase from "./pages/CreateCase";
import CaseLayout from "./pages/CaseLayout";
import Summary from "./pages/case/Summary";
import Upload from "./pages/case/Upload";
import Documents from "./pages/case/Documents";
import DocumentViewer from "./pages/case/DocumentViewer";
import ExtractionReview from "./pages/case/ExtractionReview";
import FindingsHub from "./pages/case/FindingsHub";
import Financial from "./pages/case/Financial";
import EvidenceGraph from "./pages/case/EvidenceGraph";
import Forensics from "./pages/case/Forensics";
import Assistant from "./pages/case/Assistant";
import RiskPage from "./pages/case/Risk";
import Vault from "./pages/case/Vault";
import Reports from "./pages/case/Reports";
import Audit from "./pages/Audit";
import SettingsPage from "./pages/Settings";

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/login" element={<Login />} />
              <Route element={<RequireAuth><Layout /></RequireAuth>}>
                <Route path="overview" element={<Overview />} />
                <Route path="scan" element={<Scan />} />
                <Route path="scan/:portal" element={<Scan />} />
                <Route path="compare" element={<Compare />} />
                <Route path="investigate" element={<Investigate />} />
                <Route path="cases" element={<Cases />} />
                <Route path="cases/new" element={<CreateCase />} />
                <Route path="cases/:caseId" element={<CaseLayout />}>
                  <Route index element={<Navigate to="summary" replace />} />
                  <Route path="summary" element={<Summary />} />
                  <Route path="upload" element={<Upload />} />
                  <Route path="documents" element={<Documents />} />
                  <Route path="documents/:docId" element={<DocumentViewer />} />
                  <Route path="review/:docId" element={<ExtractionReview />} />
                  <Route path="findings" element={<FindingsHub />} />
                  <Route path="identity" element={<Navigate to="../findings" replace />} />
                  <Route path="cross" element={<Navigate to="../findings" replace />} />
                  <Route path="financial" element={<Financial />} />
                  <Route path="graph" element={<EvidenceGraph />} />
                  <Route path="forensics" element={<Forensics />} />
                  <Route path="assistant" element={<Assistant />} />
                  <Route path="risk" element={<RiskPage />} />
                  <Route path="vault" element={<Vault />} />
                  <Route path="reports" element={<Reports />} />
                  <Route path="audit" element={<Audit />} />
                </Route>
                <Route path="audit" element={<Audit />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}