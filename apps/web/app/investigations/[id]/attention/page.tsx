import { AppShell } from "../../../../components/app-shell";
import { CloseAttentionPage } from "../../../../components/close-workflow";

export default async function InvestigationAttentionRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><CloseAttentionPage investigationId={id} /></AppShell>;
}
