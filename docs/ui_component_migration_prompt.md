# FinTrace UI Component Migration Prompt

Use the following prompt for a future implementation task. It is intentionally strict: do not mark the task complete because the application builds while the component boundary is still non-compliant.

```text
Act as a senior frontend architect and shadcn/ui maintainer. Refactor the FinTrace repository so the shared UI architecture is correct and enforceable.

Read first:
- AGENTS.md
- docs/PRD.md
- docs/architecture.md
- docs/standards.md
- docs/requirements.md
- docs/phase_scope.md
- docs/decisions.md
- the complete current apps/web and packages/ui source tree

Goal
Implement one centralized, reusable shadcn-style component system under packages/ui/src/components. The web app must compose that system; it must not own duplicate primitives, palette definitions, or global CSS. Keep shared global infrastructure such as packages/ui/src/global.css, packages/ui/src/index.ts, packages/ui/src/utils.ts, and packages/ui/src/tailwind.preset.ts directly under packages/ui/src.

Non-negotiable rules
1. Every reusable UI component used by any app belongs in packages/ui/src/components.
2. Create one focused file per primitive under packages/ui/src/components: button.tsx, card.tsx, badge.tsx, progress.tsx, dropdown-menu.tsx, input.tsx, select.tsx, dialog.tsx, table.tsx, tabs.tsx, tooltip.tsx, separator.tsx, skeleton.tsx, alert.tsx, and any other component the current product actually uses. Do not create components merely to inflate the inventory.
3. If a primitive has multiple variants or sizes, keep every variant, size, and state in that primitive's one file using cva or the equivalent shadcn pattern. Do not split Button variants into app files.
4. Export every public component and utility from packages/ui/src/index.ts (or the package's public barrel). Apps import components only through @fintrace/ui.
5. Add packages/ui/src/global.css. It is the single source of resets, typography, semantic CSS variables, themes, focus states, shared utility classes, and global styles.
6. Replace apps/web/app/globals.css with exactly one import of the shared stylesheet. It must contain no Tailwind directives, selectors, color values, keyframes, utilities, or comments beyond the import if the build requires none.
7. Remove duplicate or dead app-local primitive implementations. Product components may remain in apps/web/components only when they compose shared primitives and contain product-specific layout/behavior, not generic UI.
8. Remove all hardcoded colors from packages/ui/src and apps/web: no hex/rgb/hsl values, Tailwind palette utilities such as bg-slate-900/text-white/border-slate-200, inline color styles, or product-specific color constants in JSX/TSX/CSS. Use semantic tokens such as bg-background, text-foreground, bg-primary, text-primary-foreground, border-border, text-muted-foreground, bg-destructive, and ring-ring.
9. Map semantic Tailwind utilities to CSS variables in the shared UI Tailwind preset/config. Do not redefine a second palette in apps/web. Keep theme values in global.css under explicit namespaces such as :root and [data-theme="operations"].
10. Preserve the visual intent and accessibility of the current product. Keep keyboard focus, disabled states, contrast, loading/empty/error states, responsive behavior, and semantic HTML.
11. Do not move product data or business rules into packages/ui.
12. Do not change API contracts, domain rules, reconciliation behavior, or product scope. If a required change affects behavior, update docs/PRD.md and the relevant docs in the same change.

Required implementation sequence
A. Inventory every reusable visual primitive and every import in apps/web.
B. Design the token contract and semantic Tailwind mapping before rewriting components.
C. Create/migrate the component files and public exports.
D. Move global CSS into packages/ui/src/global.css and make each app stylesheet one import.
E. Replace app imports and markup with shared components and semantic token classes.
F. Remove duplicate implementations and dead component copies.
G. Add static guard scripts/tests for: one-line app globals.css, no literal colors, no forbidden palette classes, public export coverage, and no app-local primitive duplicates.
H. Update docs/architecture.md, docs/standards.md, docs/requirements.md, docs/phase_scope.md, docs/decisions.md, docs/review_protocol.md, and docs/PRD.md if behavior/scope changed.

Verification gates — all must pass
1. pnpm lint
2. pnpm typecheck
3. pnpm build
4. UI component tests or route smoke tests cover every exported component that is used by the product.
5. A static scan proves apps/web/app/globals.css has exactly one import and no declarations.
6. A static scan proves no forbidden literal colors or Tailwind palette utilities remain in packages/ui/src or apps/web.
7. A static scan proves every reusable component import resolves through @fintrace/ui and no duplicate app-local primitive exists.
8. Browser smoke-test every route in docs/appflow.md at narrow, tablet, and desktop widths, including loading, empty, error, focus, and interactive states.
9. Compare the rendered UI against the pre-refactor baseline and fix regressions; do not accept a build-only result.
10. Report exact files changed, checks run, results, remaining limitations, and the final component inventory. Do not claim completion if any rule or gate is unmet.

Use apply_patch for source edits, keep changes focused, and preserve all unrelated user work.
```
