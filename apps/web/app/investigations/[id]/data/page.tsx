import { AppShell } from "../../../../components/app-shell";
import { CloseDataPage } from "../../../../components/close-workflow";

export default async function InvestigationDataRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><CloseDataPage investigationId={id} /></AppShell>;
}
