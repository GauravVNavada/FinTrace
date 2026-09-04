import { AppShell } from "../../../../components/app-shell";
import { CloseReconciliationPage } from "../../../../components/close-workflow";

export default async function InvestigationReconciliationRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><CloseReconciliationPage investigationId={id} /></AppShell>;
}
