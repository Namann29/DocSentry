import { Outlet, useParams } from "react-router-dom";
import { useCase } from "../api/hooks";
import { ErrorBox, Skeleton } from "../components/ui";

export default function CaseLayout() {
  const id = Number(useParams().caseId);
  const c = useCase(id);
  if (c.isLoading) return <Skeleton rows={6} />;
  if (c.error || !c.data) return <ErrorBox error={c.error ?? "Case not found"} />;
  return <Outlet context={c.data} />;
}