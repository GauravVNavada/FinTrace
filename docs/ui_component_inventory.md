# FinTrace UI Component Inventory

**Status:** Implemented for the current web surface · 2026-08-31
**Owner:** Web platform / design system  
**Authority:** `docs/ui_component_migration_prompt.md`, `docs/standards.md`, and ADR-006 in `docs/decisions.md`

## Purpose

This document is the implementation inventory for the shared UI boundary. It records which presentation primitives exist, where their variants live, how the web app consumes them, and which automated checks protect the boundary.

The inventory is intentionally limited to primitives needed by the current product. New primitives are added only when a route needs them or when an explicit component test justifies them. Product data, domain rules, API clients, and route-specific composition remain in `apps/web` or `apps/api`.

## Ownership rules

1. `packages/ui/src/components` is the only home for reusable presentation primitives; global infrastructure remains directly under `packages/ui/src`.
2. Each primitive has one focused source file; its variants, sizes, and state styling stay in that file.
3. `packages/ui/src/index.ts` is the public package surface. Web code imports primitives from `@fintrace/ui`.
4. `packages/ui/src/global.css` owns reset, typography, semantic variables, themes, focus treatment, and shared global utilities.
5. Every web app stylesheet contains exactly one import of the shared stylesheet.
6. Product screens use semantic Tailwind utilities. Literal color values, palette utilities, and inline color styles are prohibited in app markup and shared components.
7. The UI package has no product data or business policy.

## Primitive inventory

| Primitive file | Public exports | Current route/component consumers | Verification |
| --- | --- | --- | --- |
| `components/alert.tsx` | `Alert`, `AlertTitle`, `AlertDescription` | Patterns, evaluations, audit, dashboard empty state | `check:ui-architecture`; route smoke |
| `components/badge.tsx` | `Badge` | Status/severity badges, pattern state labels | `check:ui-architecture`; route smoke |
| `components/button.tsx` | `Button`, `buttonVariants` | Shell actions, filters, queue, detail actions, controls | `check:ui-architecture`; route smoke |
| `components/card.tsx` | `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter` | All dashboard and product panels; loading state | `check:ui-architecture`; route smoke |
| `components/input.tsx` | `Input` | Shell search, exception queue search, investigation form | `check:ui-architecture`; interaction smoke |
| `components/file-input.tsx` | `FileInput` | Investigation source intake | `check:ui-architecture`; upload interaction smoke |
| `components/progress.tsx` | `Progress` | Reconciliation health and evidence score | `check:ui-architecture`; route smoke |
| `components/select.tsx` | `Select` | Exception severity and lifecycle filters | `check:ui-architecture`; interaction smoke |
| `components/separator.tsx` | `Separator` | Responsive shell header | `check:ui-architecture`; route smoke |
| `components/skeleton.tsx` | `Skeleton` | App Router loading boundary | `check:ui-architecture`; loading route smoke |
| `components/table.tsx` | `Table`, `TableHeader`, `TableBody`, `TableFooter`, `TableHead`, `TableRow`, `TableCell`, `TableCaption` | Queue and reconciliation-run tables | `check:ui-architecture`; route smoke |
| `components/textarea.tsx` | `Textarea` | Investigation description form | `check:ui-architecture`; interaction smoke |

`CardDescription`, `CardFooter`, `TableFooter`, and `TableCaption` are composable subparts of the route-used Card/Table families. They are exported together with their parent family so future screens do not create local structural variants.

## Token and theme contract

The shared stylesheet defines semantic variables for background/foreground, card/popover, primary/secondary/muted/accent, destructive/warning/success/info, border/input/ring, and sidebar surfaces. The Tailwind preset maps those variables to semantic utility names. The operations theme is selected at the app shell boundary with `data-theme="operations"`; no app-local palette is defined.

The generated product mark at `apps/web/public/fintrace-mark.png` is a brand asset, not a source of UI colors. The favicon is the code-native `apps/web/app/icon.svg` and is declared through the App Router metadata.

## Quality gates

Run these commands from the repository root:

```text
pnpm check:ui-architecture
pnpm lint
pnpm typecheck
pnpm build
```

`check:ui-architecture` verifies the one-line stylesheet boundary, required primitive files and barrel exports, forbidden palette/literal-color patterns in source, native control duplication, and app-local primitive filenames. Browser smoke additionally checks all stable routes at desktop, tablet, and mobile widths, plus search/filter and investigation/review interactions.

## Change procedure

When a new reusable primitive or token is required:

1. Update this inventory and the relevant requirement/architecture/standards decision documents.
2. Add the focused primitive under `packages/ui/src/components`, export it from `index.ts`, and use semantic tokens. Keep global infrastructure such as `global.css`, `utils.ts`, and the Tailwind preset outside that folder.
3. Add or update a route-level loading, empty, error, keyboard, and disabled state as applicable.
4. Update the UI architecture guard and run the full quality gates.
5. Update `docs/PRD.md` when the visible product scope or behavior changes; do not silently change the plan.
