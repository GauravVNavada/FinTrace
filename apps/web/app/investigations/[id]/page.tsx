import { AppShell } from "../../../components/app-shell";
import { FinancialInvestigationDetailPage, InvestigationStageNav } from "../../../components/financial-investigations";

export default async function InvestigationRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><InvestigationStageNav investigationId={id} /><FinancialInvestigationDetailPage investigationId={id} /></AppShell>;
}
