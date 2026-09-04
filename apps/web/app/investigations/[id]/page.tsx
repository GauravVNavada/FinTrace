import { AppShell } from "../../../components/app-shell";
import { CloseOverviewPage } from "../../../components/close-workflow";

export default async function InvestigationRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><CloseOverviewPage investigationId={id} /></AppShell>;
}
