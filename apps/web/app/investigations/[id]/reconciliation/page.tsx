import { AppShell } from "../../../../components/app-shell";
import { CloseResultsPage } from "../../../../components/close-workflow";

export default async function InvestigationReconciliationRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><CloseResultsPage investigationId={id} /></AppShell>;
}
