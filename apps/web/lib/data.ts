const configuredRole = process.env.NEXT_PUBLIC_ACTOR_ROLE ?? "ANALYST";
const actorRoleLabel = configuredRole.replaceAll("_", " ").toLowerCase().replace(/(^| )\w/g, character => character.toUpperCase());

export const appConfig = {
  productName: "FinTrace",
  workspaceName: "Northstar Retail Group",
  workspaceEnvironment: "Local demo",
  currency: "INR" as const,
  benchmark: { orders: 1000, seed: 42, anomalyRate: 0.30 },
  actor: { name: "Aarav Mehta", firstName: "Aarav", initials: "AM", role: actorRoleLabel }
};

export function formatCurrency(value: number, currency = "INR") {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(value);
}
