import { AppShell } from "../../../components/app-shell";
import { FinancialInvestigationDetailPage } from "../../../components/financial-investigations";

export default async function InvestigationRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><FinancialInvestigationDetailPage investigationId={id} /></AppShell>;
}
