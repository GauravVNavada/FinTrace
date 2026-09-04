"use client";

import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { BookOpen, CircleHelp, FileBarChart, FolderSearch, LayoutDashboard, LogOut, Network, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button, cn } from "@fintrace/ui";
import { appConfig } from "../lib/data";
import { fetchReadiness, getClientIdentity } from "../lib/api-client";

type NavItem = { label: string; href: string; icon: LucideIcon };
type Panel = "help" | null;

const navGroups: Array<{ label: string; items: NavItem[] }> = [
  { label: "Workspace", items: [{ label: "Overview", href: "/", icon: LayoutDashboard }, { label: "Investigations", href: "/investigations", icon: FolderSearch }, { label: "Patterns", href: "/patterns", icon: Network }] },
  { label: "Controls", items: [{ label: "Evaluations", href: "/evaluations", icon: FileBarChart }, { label: "Audit", href: "/audit", icon: ShieldCheck }] }
];

function Navigation({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();
  return <nav aria-label="Primary navigation" className={cn(mobile ? "flex gap-1 overflow-x-auto px-4 py-2 lg:hidden" : "flex-1 px-3 py-5")}>{navGroups.map(group => <div key={group.label} className={cn(mobile ? "flex shrink-0 gap-1" : "mb-7 last:mb-0")}>{!mobile && <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-sidebar-muted">{group.label}</div>}{group.items.map(item => { const Icon = item.icon; const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href); return <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={cn("flex items-center gap-3 rounded-md text-[13px] font-medium transition-colors", mobile ? "whitespace-nowrap px-3 py-2" : "mb-1 px-3 py-2.5", active ? "bg-sidebar-accent text-sidebar-foreground" : "text-sidebar-muted hover:bg-sidebar-accent/70 hover:text-sidebar-foreground")}><Icon className={cn("h-4 w-4", active ? "text-accent" : "text-sidebar-muted")} />{item.label}</Link>; })}</div>)}</nav>;
}

function HeaderPanel({ onClose }: { onClose: () => void }) {
  return <div className="absolute right-4 top-14 z-20 w-72 rounded-lg border border-border bg-card p-4 text-xs shadow-lg"><div className="font-semibold text-foreground">FinTrace help</div><p className="mt-2 leading-5 text-muted-foreground">Use Investigations to complete a close: understand sources, reconcile lifecycles, and work only the attention items that need a decision or approval.</p><div className="mt-2 flex items-center gap-3"><Button asChild variant="link" size="sm" className="px-0"><Link href="/guide">Open usage guide</Link></Button><Button variant="link" size="sm" className="px-0" onClick={onClose}>Close</Button></div></div>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [panel, setPanel] = React.useState<Panel>(null);
  const [identity, setIdentity] = React.useState(getClientIdentity);
  const [apiState, setApiState] = React.useState<"checking" | "connected" | "unavailable">("checking");
  function logout() {
    window.localStorage.removeItem("fintrace.access_token");
    window.localStorage.removeItem("fintrace.identity");
    router.replace("/login");
  }
  React.useEffect(() => {
    if (!pathname.startsWith("/login") && !window.localStorage.getItem("fintrace.access_token")) { router.replace("/login"); return; }
    setIdentity(getClientIdentity());
    fetchReadiness().then(() => setApiState("connected")).catch(() => setApiState("unavailable"));
  }, [pathname, router]);
  const apiLabel = apiState === "connected" ? "Data API ready" : apiState === "unavailable" ? "Data API unavailable" : "Checking data API";
  const apiTone = apiState === "connected" ? "bg-success" : apiState === "unavailable" ? "bg-destructive" : "bg-warning";
  return <div data-theme="operations" className="flex min-h-screen bg-background"><a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2 focus:text-xs focus:font-semibold focus:text-foreground focus:shadow-lg">Skip to main content</a><aside className="fixed inset-y-0 left-0 z-20 hidden w-[244px] flex-col bg-sidebar text-sidebar-foreground lg:flex"><div className="flex h-[76px] items-center border-b border-sidebar-border px-5"><Image src="/fintrace-mark.png" alt="" aria-hidden="true" width={32} height={32} className="rounded-lg object-cover" priority /><div className="ml-3"><div className="text-[15px] font-bold tracking-tight">{appConfig.productName}</div><div className="text-[10px] uppercase tracking-[0.18em] text-sidebar-muted">Operations console</div></div></div><div className="border-b border-sidebar-border px-4 py-4"><div className="rounded-md border border-sidebar-border bg-sidebar-accent/70 px-3 py-2.5"><div className="text-xs font-semibold">{appConfig.workspaceName}</div><div className="mt-0.5 text-[10px] text-sidebar-muted">{appConfig.workspaceEnvironment}</div></div></div><Navigation /><div className="border-t border-sidebar-border px-3 py-4"><Link href="/guide" className="mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-[13px] font-medium text-sidebar-muted hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"><BookOpen className="h-4 w-4" />How to use</Link><div className="mt-4 flex items-center gap-3 px-3"><div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-accent text-[11px] font-bold text-sidebar-foreground">{identity.display_name.split(" ").map(part => part[0]).join("").slice(0, 2)}</div><div><div className="text-xs font-semibold">{identity.display_name}</div><div className="text-[10px] text-sidebar-muted">{identity.role.replaceAll("_", " ")}</div></div></div><Button variant="ghost" size="sm" className="mt-3 w-full justify-start gap-3 px-3 text-sidebar-muted hover:bg-sidebar-accent/70 hover:text-sidebar-foreground" onClick={logout}><LogOut className="h-4 w-4" />Log out</Button></div></aside><div className="flex min-h-screen min-w-0 flex-1 flex-col lg:pl-[244px]"><header className="sticky top-0 z-10 border-b border-border bg-card/90 backdrop-blur"><div className="relative flex h-[68px] items-center justify-between px-4 sm:px-5 lg:h-[76px] lg:px-8"><div className="flex min-w-0 items-center gap-3"><span className="text-xs font-medium text-muted-foreground">{appConfig.productName} / Financial close</span></div><div className="flex items-center gap-2 sm:gap-3"><div className="flex items-center gap-2 text-xs font-medium text-muted-foreground" aria-live="polite"><span className={cn("h-2 w-2", apiTone)} />{apiLabel}</div><div className="hidden items-center gap-2 text-xs font-semibold text-info sm:flex">{identity.role.replaceAll("_", " ")}</div><Button variant="outline" size="sm" className="gap-2" onClick={logout}><LogOut className="h-3.5 w-3.5" /><span className="hidden sm:inline">Log out</span></Button><Button variant="ghost" size="icon" className="text-muted-foreground" aria-label="Help" aria-expanded={panel === "help"} onClick={() => setPanel(panel === "help" ? null : "help")}><CircleHelp className="h-[18px] w-[18px]" aria-hidden="true" /> </Button>{panel && <HeaderPanel onClose={() => setPanel(null)} />}</div></div><Navigation mobile /></header><main id="main-content" tabIndex={-1} className="flex-1 px-4 py-6 outline-none sm:px-5 lg:px-8 lg:py-7">{children}</main><footer className="border-t border-border px-4 py-4 text-[11px] text-muted-foreground sm:px-8">{appConfig.productName} local demo · Synthetic data only · {apiLabel}</footer></div></div>;
}
