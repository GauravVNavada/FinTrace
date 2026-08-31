import { AppShell } from "../../../../components/app-shell";
import { FinancialInvestigationSourcesPage } from "../../../../components/financial-investigations";

export default async function InvestigationSourcesRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><FinancialInvestigationSourcesPage investigationId={id} /></AppShell>;
}
