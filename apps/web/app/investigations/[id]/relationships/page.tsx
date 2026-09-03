import { AppShell } from "../../../../components/app-shell";
import { InvestigationStageNav, RelationshipReview } from "../../../../components/financial-investigations";

export default async function RelationshipsRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><InvestigationStageNav investigationId={id} /><RelationshipReview investigationId={id} /></AppShell>;
}
