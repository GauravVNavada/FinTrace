export type AuditAccess = "available" | "forbidden" | "unavailable";

export type ExceptionDetailLoaders<
  TException extends { id: string; order_id: string },
  TLifecycle,
  TAuditEvent,
> = {
  fetchException: (exceptionId: string) => Promise<TException>;
  fetchLifecycle: (orderId: string) => Promise<TLifecycle>;
  fetchAuditEvents: (resourceId: string) => Promise<TAuditEvent[]>;
  isForbiddenError?: (error: unknown) => boolean;
};

export async function loadExceptionDetail<
  TException extends { id: string; order_id: string },
  TLifecycle,
  TAuditEvent,
>(
  exceptionId: string,
  loaders: ExceptionDetailLoaders<TException, TLifecycle, TAuditEvent>,
): Promise<{
  exception: TException;
  lifecycle: TLifecycle;
  auditEvents: TAuditEvent[];
  auditAccess: AuditAccess;
}> {
  const exception = await loaders.fetchException(exceptionId);
  const [lifecycle, audit] = await Promise.all([
    loaders.fetchLifecycle(exception.order_id),
    loaders.fetchAuditEvents(exception.id)
      .then(auditEvents => ({ auditEvents, auditAccess: "available" as const }))
      .catch(error => ({
        auditEvents: [] as TAuditEvent[],
        auditAccess: loaders.isForbiddenError?.(error) ? "forbidden" as const : "unavailable" as const,
      })),
  ]);

  return { exception, lifecycle, ...audit };
}
