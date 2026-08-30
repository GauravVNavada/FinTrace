"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, ChevronDown, CircleHelp, FileBarChart, LayoutDashboard, ListFilter, Network, Search, Settings2, ShieldCheck, WalletCards } from "lucide-react";
import { appConfig } from "../lib/data";
import { cn } from "@fintrace/ui";

const navGroups = [
  { label: "Workspace", items: [{ label: "Overview", href: "/", icon: LayoutDashboard }, { label: "Exceptions", href: "/exceptions", icon: ListFilter }, { label: "Patterns", href: "/patterns", icon: Network }] },
  { label: "Controls", items: [{ label: "Reconciliation runs", href: "/runs", icon: WalletCards }, { label: "Evaluations", href: "/evaluations", icon: FileBarChart }, { label: "Audit trail", href: "/audit", icon: ShieldCheck }] }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return <div className="flex min-h-screen bg-canvas">
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-[244px] flex-col bg-navy text-slate-300 lg:flex">
      <div className="flex h-[76px] items-center border-b border-white/10 px-5"><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-400 text-sm font-black text-slate-950">F</div><div className="ml-3"><div className="text-[15px] font-bold tracking-tight text-white">FinTrace</div><div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Operations console</div></div></div>
      <div className="border-b border-white/10 px-4 py-4"><button className="flex w-full items-center gap-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2.5 text-left hover:bg-white/10"><div className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-400/20 text-xs font-bold text-indigo-200">NR</div><div className="min-w-0 flex-1"><div className="truncate text-xs font-semibold text-white">{appConfig.workspaceName}</div><div className="mt-0.5 text-[10px] text-slate-500">Production workspace</div></div><ChevronDown className="h-4 w-4 text-slate-500" /></button></div>
      <nav className="flex-1 px-3 py-5">{navGroups.map(group => <div key={group.label} className="mb-7"><div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">{group.label}</div>{group.items.map(item => { const Icon = item.icon; const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href); return <Link key={item.href} href={item.href} className={cn("mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-[13px] font-medium transition-colors", active ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white")}><Icon className={cn("h-4 w-4", active ? "text-emerald-300" : "text-slate-500")} />{item.label}{item.label === "Exceptions" && <span className="ml-auto rounded-full bg-rose-500/15 px-1.5 py-0.5 text-[10px] font-bold text-rose-300">56</span>}</Link> })}</div>)}</nav>
      <div className="border-t border-white/10 px-3 py-4"><Link href="/settings" className="mb-1 flex items-center gap-3 rounded-md px-3 py-2.5 text-[13px] font-medium text-slate-400 hover:bg-white/5 hover:text-white"><Settings2 className="h-4 w-4 text-slate-500" />Settings</Link><div className="mt-4 flex items-center gap-3 px-3"><div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-700 text-[11px] font-bold text-slate-200">AM</div><div><div className="text-xs font-semibold text-white">Aarav Mehta</div><div className="text-[10px] text-slate-500">Finance analyst</div></div></div></div>
    </aside>
    <div className="flex min-h-screen min-w-0 flex-1 flex-col lg:pl-[244px]">
      <header className="sticky top-0 z-10 flex h-[76px] items-center justify-between border-b border-line bg-white/90 px-5 backdrop-blur lg:px-8"><div className="flex items-center gap-3"><div className="lg:hidden flex h-8 w-8 items-center justify-center rounded-lg bg-navy text-sm font-black text-white">F</div><div className="relative hidden w-[300px] md:block"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><input placeholder="Search orders, exceptions..." className="h-9 w-full rounded-md border border-slate-200 bg-slate-50 pl-9 pr-3 text-xs outline-none placeholder:text-slate-400 focus:border-slate-400" /></div><div className="hidden text-xs text-slate-500 md:block">/</div></div><div className="flex items-center gap-3"><button className="relative rounded-md p-2 text-slate-500 hover:bg-slate-100"><Bell className="h-[18px] w-[18px]" /><span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-rose-500" /></button><div className="hidden h-5 w-px bg-slate-200 sm:block" /><div className="flex items-center gap-2 text-xs font-medium text-slate-600"><div className="h-2 w-2 rounded-full bg-emerald-500" />All systems operational</div><button className="rounded-md p-2 text-slate-500 hover:bg-slate-100"><CircleHelp className="h-[18px] w-[18px]" /></button></div></header>
      <main className="flex-1 px-5 py-7 lg:px-8">{children}</main>
      <footer className="border-t border-line px-8 py-4 text-[11px] text-slate-400">FinTrace demo environment · Synthetic data only · Last synced {appConfig.lastSynced}</footer>
    </div>
  </div>;
}
