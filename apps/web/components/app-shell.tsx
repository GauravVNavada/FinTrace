"use client";

import type { LucideIcon } from "lucide-react";
import { Bell, ChevronDown, CircleHelp, FileBarChart, LayoutDashboard, ListFilter, Network, Search, Settings2, ShieldCheck, WalletCards } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button, Input, Separator, cn } from "@fintrace/ui";
import { appConfig } from "../lib/data";

type NavItem = { label: string; href: string; icon: LucideIcon };

const navGroups: Array<{ label: string; items: NavItem[] }> = [
  { label: "Workspace", items: [{ label: "Overview", href: "/", icon: LayoutDashboard }, { label: "Exceptions", href: "/exceptions", icon: ListFilter }, { label: "Patterns", href: "/patterns", icon: Network }] },
  { label: "Controls", items: [{ label: "Reconciliation runs", href: "/runs", icon: WalletCards }, { label: "Evaluations", href: "/evaluations", icon: FileBarChart }, { label: "Audit trail", href: "/audit", icon: ShieldCheck }] }
];

function Navigation({ mobile = false }: { mobile?: boolean }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Primary navigation" className={cn(mobile ? "flex gap-1 overflow-x-auto px-4 py-2 lg:hidden" : "flex-1 px-3 py-5")}>
      {navGroups.map(group => (
        <div key={group.label} className={cn(mobile ? "flex shrink-0 gap-1" : "mb-7 last:mb-0")}>
          {!mobile && <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-sidebar-muted">{group.label}</div>}
          {group.items.map(item => {
            const Icon = item.icon;
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={cn("flex items-center gap-3 rounded-md text-[13px] font-medium transition-colors", mobile ? "whitespace-nowrap px-3 py-2" : "mb-1 px-3 py-2.5", active ? "bg-sidebar-accent text-sidebar-foreground" : "text-sidebar-muted hover:bg-sidebar-accent/70 hover:text-sidebar-foreground")}>
                <Icon className={cn("h-4 w-4", active ? "text-accent" : "text-sidebar-muted")} />
                {item.label}
                {item.label === "Exceptions" && <span className="ml-auto rounded-full bg-destructive/15 px-1.5 py-0.5 text-[10px] font-bold text-destructive">{appConfig.unresolvedExceptions}</span>}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div data-theme="operations" className="flex min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[244px] flex-col bg-sidebar text-sidebar-foreground lg:flex">
        <div className="flex h-[76px] items-center border-b border-sidebar-border px-5"><Image src="/fintrace-mark.png" alt="" aria-hidden="true" width={32} height={32} className="rounded-lg object-cover" priority /><div className="ml-3"><div className="text-[15px] font-bold tracking-tight">{appConfig.productName}</div><div className="text-[10px] uppercase tracking-[0.18em] text-sidebar-muted">Operations console</div></div></div>
        <div className="border-b border-sidebar-border px-4 py-4"><Button variant="ghost" className="h-auto w-full justify-start border border-sidebar-border bg-sidebar-accent/70 px-3 py-2.5 text-left text-sidebar-foreground hover:bg-sidebar-accent"><span className="flex h-7 w-7 items-center justify-center rounded-md bg-info/20 text-xs font-bold text-info">NR</span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-semibold">{appConfig.workspaceName}</span><span className="mt-0.5 block text-[10px] text-sidebar-muted">{appConfig.workspaceEnvironment}</span></span><ChevronDown className="h-4 w-4 text-sidebar-muted" /></Button></div>
        <Navigation />
        <div className="border-t border-sidebar-border px-3 py-4"><Link href="/settings" className="mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-[13px] font-medium text-sidebar-muted hover:bg-sidebar-accent/70 hover:text-sidebar-foreground"><Settings2 className="h-4 w-4" />Settings</Link><div className="mt-4 flex items-center gap-3 px-3"><div className="flex h-8 w-8 items-center justify-center rounded-full bg-sidebar-accent text-[11px] font-bold text-sidebar-foreground">{appConfig.actor.initials}</div><div><div className="text-xs font-semibold">{appConfig.actor.name}</div><div className="text-[10px] text-sidebar-muted">{appConfig.actor.role}</div></div></div></div>
      </aside>
      <div className="flex min-h-screen min-w-0 flex-1 flex-col lg:pl-[244px]">
        <header className="sticky top-0 z-10 border-b border-border bg-card/90 backdrop-blur"><div className="flex h-[68px] items-center justify-between px-4 sm:px-5 lg:h-[76px] lg:px-8"><div className="flex min-w-0 items-center gap-3"><div className="relative hidden w-[300px] md:block"><Search aria-hidden="true" className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" /><Input aria-label="Search orders and exceptions" placeholder="Search orders, exceptions…" className="bg-muted/50 pl-9 text-xs" /></div><span className="hidden text-xs text-muted-foreground md:block">/</span><span className="truncate text-xs font-medium text-muted-foreground md:hidden">{appConfig.productName}</span></div><div className="flex items-center gap-2 sm:gap-3"><Button variant="ghost" size="icon" className="relative text-muted-foreground" aria-label="Notifications"><Bell className="h-[18px] w-[18px]" /><span aria-label="Unread notifications" className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-destructive" /></Button><Separator orientation="vertical" className="hidden h-5 sm:block" /><div className="hidden items-center gap-2 text-xs font-medium text-muted-foreground sm:flex"><span className="h-2 w-2 rounded-full bg-success" />All systems operational</div><Button variant="ghost" size="icon" className="text-muted-foreground" aria-label="Help"><CircleHelp className="h-[18px] w-[18px]" /></Button></div></div><Navigation mobile /></header>
        <main className="flex-1 px-4 py-6 sm:px-5 lg:px-8 lg:py-7">{children}</main>
        <footer className="border-t border-border px-4 py-4 text-[11px] text-muted-foreground sm:px-8">{appConfig.productName} demo environment · Synthetic data only · Last synced {appConfig.lastSynced}</footer>
      </div>
    </div>
  );
}
