import { AppShell } from "../../../components/app-shell";
import { ExceptionDetail } from "../../../components/exception-detail";

export default async function ExceptionRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AppShell><ExceptionDetail id={id} /></AppShell>;
}
