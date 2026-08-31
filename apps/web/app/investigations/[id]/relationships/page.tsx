import { AppShell } from "../../../../components/app-shell";
import { RelationshipReview } from "../../../../components/financial-investigations";

export default async function RelationshipsRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><RelationshipReview investigationId={id} /></AppShell>;
}
