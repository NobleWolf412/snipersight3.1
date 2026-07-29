---
name: SniperSight
description: Tactical HUD for SMC trading intelligence
colors:
  bg: "oklch(0.18 0.008 120)"
  bg-2: "oklch(0.22 0.010 125)"
  card: "oklch(0.26 0.012 125)"
  card-2: "oklch(0.30 0.012 125)"
  border: "oklch(0.36 0.015 130)"
  border-soft: "oklch(0.32 0.015 130 / 0.6)"
  fg: "oklch(0.94 0.012 150)"
  fg-2: "oklch(0.78 0.012 150)"
  fg-3: "oklch(0.58 0.015 150)"
  fg-4: "oklch(0.42 0.012 150)"
  green: "#00ffaa"
  green-soft: "#4ade80"
  amber: "#ffc266"
  amber-2: "#fbbf24"
  red: "#ff6464"
  red-2: "#f87171"
  blue: "#60a5fa"
  cyan: "#22d3ee"
  purple: "#c084fc"
typography:
  display:
    fontFamily: "'Share Tech Mono', ui-monospace, monospace"
    fontSize: "clamp(38px, 5.4vw, 68px)"
    fontWeight: 400
    lineHeight: "0.98"
    letterSpacing: "0.01em"
  page-title:
    fontFamily: "'Share Tech Mono', monospace"
    fontSize: "32px"
    fontWeight: 400
    lineHeight: "1"
    letterSpacing: "0.2em"
  section-title:
    fontFamily: "'Share Tech Mono', monospace"
    fontSize: "13px"
    fontWeight: 400
    letterSpacing: "0.22em"
  metric-value:
    fontFamily: "'Share Tech Mono', 'JetBrains Mono', monospace"
    fontSize: "26px"
    fontWeight: 800
    lineHeight: "1"
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "1.55"
    letterSpacing: "normal"
  label:
    fontFamily: "'JetBrains Mono', monospace"
    fontSize: "10px"
    fontWeight: 600
    letterSpacing: "0.18em"
  mono:
    fontFamily: "'JetBrains Mono', monospace"
    fontSize: "11.5px"
    fontWeight: 400
    fontFeature: "tabular-nums"
rounded:
  sm: "8px"
  md: "10px"
  lg: "12px"
  xl: "14px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "18px"
  xl: "24px"
  shell-x: "28px"
components:
  panel:
    backgroundColor: "linear-gradient(135deg, rgba(0,0,0,0.55), oklch(0.22 0.010 125 / 0.6))"
    textColor: "{colors.fg}"
    rounded: "{rounded.xl}"
    padding: "0"
  chip:
    backgroundColor: "rgba(255,255,255,0.04)"
    textColor: "{colors.fg-2}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
    typography: "{typography.label}"
  chip-accent:
    backgroundColor: "rgba(0,255,170,0.10)"
    textColor: "{colors.green}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  chip-red:
    backgroundColor: "rgba(248,113,113,0.08)"
    textColor: "{colors.red-2}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  chip-cyan:
    backgroundColor: "rgba(34,211,238,0.08)"
    textColor: "{colors.cyan}"
    rounded: "{rounded.pill}"
    padding: "3px 8px"
  btn:
    backgroundColor: "rgba(255,255,255,0.03)"
    textColor: "{colors.fg-2}"
    rounded: "{rounded.md}"
    padding: "9px 14px"
  btn-cyan:
    backgroundColor: "linear-gradient(180deg, #164e63 0%, #0e3a4a 60%, #0a2d3a 100%)"
    textColor: "#67e8f9"
    rounded: "{rounded.md}"
    padding: "9px 14px"
  btn-red:
    backgroundColor: "rgba(248,113,113,0.10)"
    textColor: "{colors.red-2}"
    rounded: "{rounded.md}"
    padding: "9px 14px"
  metric-tile:
    backgroundColor: "rgba(0,0,0,0.4)"
    textColor: "{colors.fg}"
    rounded: "{rounded.lg}"
    padding: "14px 16px"
---

# Design System: SniperSight

## 1. Overview

**Creative North Star: "The Tactical Cockpit"**

SniperSight is a HUD overlaid on a working terminal, not a dashboard with a tactical theme. Density is high, but every glyph earns its rent. The system is dark by intent: an operator scanning multi-timeframe SMC structure at 2am on a 27-inch monitor under one warm lamp, watching for the moment four signals align. Light mode is not on the roadmap.

The look reads as legible-aggressive: olive-tinted near-black surfaces, electric green as the default "GO" accent (with red on live mode and amber on warnings), mono type that owns the chrome, repeating CRT scanlines on every panel. Corner brackets and animated reticles signal that the system is *armed and watching*, not idle. Motion is restrained, repetitive, and slow: radar sweeps, pulse rings, drifting glow gradients. Nothing bounces. Nothing celebrates.

This system explicitly rejects: the generic SaaS dashboard (Inter for everything, purple-to-blue gradients, identical card grids), the consumer finance softness (rounded everything, pastels, friendly empty states), the crypto-casino aesthetic (RGB neon, gamified XP, animated charts as decoration), and AI-tool landing-page reflex (white surface, vague gradient, "intelligent trading" copy). It also refuses Bloomberg-terminal nostalgia LARP: pure `#0F0` on `#000` with unreadable density. Olive-tint backgrounds and OKLCH neutrals are the difference.

**Key Characteristics:**
- Olive-tinted dark surfaces, never pure black
- Mono type owns the chrome (Share Tech Mono for display, JetBrains Mono for labels and numbers, Inter only for prose body)
- Accent color is dynamic: green by default, amber for warnings, red for live mode
- Repeating scanlines on every `.panel` as a 2-bit overlay, not a hero effect
- Corner brackets, reticles, and orbs as ambient state indicators
- High density, low ornamentation; every chip is structural

## 2. Colors: The Olive-Tactical Palette

The system runs on tinted neutrals plus a status-coded accent family. Strategy is **Restrained at rest, Committed under state.** Tiles and panels are tinted-neutral by default; saturated color only enters via accent edges, status chips, and live-mode chrome shifts. The accent itself is a CSS variable, so a panel marked `.panel-accent` inherits whatever state the screen is in (green idle, amber armed, red live).

### Primary
- **Electric Mantis Green** (`#00ffaa`): the default accent. Used for the operating accent variable, brand mark, success states, "GO" affordances, the equity-up direction. Appears as edge glow on `.panel-accent`, as the brand text-shadow, and as the dynamic `--accent` token.

### Secondary
- **Live Mode Red** (`#ff6464` / softer `#f87171`): the live-trading state, danger affordances, sell-side direction, breach indicators. Page titles switch to red when bot mode is live. Used in `.btn-red`, `.chip-red`, `.hud-glow-red`.

### Tertiary
- **Warning Amber** (`#ffc266` / `#fbbf24`): the page-title default tone, warning chips, paper-mode demarcation, regime-cautious states. The non-live, non-success middle band.
- **Strike Cyan** (`#22d3ee`): the Strike-mode accent and the primary CTA pressable. `.btn-cyan` is the only 3D-pressable button in the system. Used sparingly.

### Neutral (olive-tinted, OKLCH)
- **Surface Deep** (`oklch(0.18 0.008 120)`): page background. Never pure black; the 0.008 chroma pulls toward olive so saturated accents read as on-brand.
- **Surface Mid** (`oklch(0.22 0.010 125)`): panel gradient lower stop, scope tile background.
- **Surface Card** (`oklch(0.26 0.012 125)`): elevated card layer.
- **Surface Card Hover** (`oklch(0.30 0.012 125)`): hover/focus elevation.
- **Border** (`oklch(0.36 0.015 130)`): hard divider, button outline default.
- **Border Soft** (`oklch(0.32 0.015 130 / 0.6)`): primary divider, panel outline.
- **FG Primary** (`oklch(0.94 0.012 150)`): primary text, metric values.
- **FG Secondary** (`oklch(0.78 0.012 150)`): body prose, button text.
- **FG Tertiary** (`oklch(0.58 0.015 150)`): nav links at rest, supporting copy.
- **FG Quaternary** (`oklch(0.42 0.012 150)`): labels, timestamps, dim metadata.

### Named Rules

**The No-Pure-Black Rule.** Surfaces are olive-tinted near-black, never `#000`. The chroma is small (0.008-0.015) but non-zero; it's what stops the HUD from feeling like a Bloomberg terminal. If you ever write `#000` or `#fff`, rewrite the value.

**The Dynamic Accent Rule.** The `--accent` token is whatever the current state mandates: green at rest, amber on warning surfaces, red in live mode. Every chip, button, panel-edge, and orb that wants the operating-state color references `var(--accent)`, not a hard-coded hue. Hard-coding green into a status-aware surface is a bug.

**The 10% Saturation Rule.** Saturated colors cover ≤10% of any single screen. Green edges, red chips, amber labels, cyan buttons: each used in pixels-not-percentages. The remaining 90% is olive-tinted neutrals. Drenched surfaces are forbidden in product register; landing is allowed exceptions.

## 3. Typography

**Display Font:** `Share Tech Mono` (with `ui-monospace, monospace` fallback)
**Body Font:** `Inter` (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Label/Mono Font:** `JetBrains Mono` (with `monospace` fallback)
**Retro Terminal:** `VT323` (used sparingly, only for `.term` artefacts)

**Character:** Mono dominates. `Share Tech Mono` carries every uppercase chrome element (brand mark, page titles, section titles, metric values, hero) with wide letter-spacing and no lowercase. `JetBrains Mono` carries every label, every chip, every numeric readout (tabular-nums, monospace digit alignment). `Inter` only enters when prose is genuinely prose: hero subhead, modal body copy, journal notes. The pairing reads as terminal-native without LARPing as one. Share Tech Mono is decorative-mono, not punch-card-mono.

### Hierarchy
- **Display** (Share Tech Mono, `clamp(38px, 5.4vw, 68px)`, weight 400, line-height 0.98, letter-spacing 0.01em): hero title on landing only. Uppercase. Used once per surface.
- **Page Title** (Share Tech Mono, 32px, weight 400, line-height 1, letter-spacing 0.2em): the `<PageHead>` h1 on every product route. Tinted amber at rest, red in live mode, with text-shadow glow.
- **Section Title** (Share Tech Mono, 13px, letter-spacing 0.22em, uppercase): panel headers. Always paired with the pulsing accent dot.
- **Metric Value** (Share Tech Mono / JetBrains Mono, 26px, weight 800, line-height 1, letter-spacing -0.01em): the prominent number on `.metric-tile`. The one place the type goes heavy.
- **Body** (Inter, 13px, weight 400, line-height 1.55): the only prose font. Used for hero subhead, modal text, journal notes. Capped at 65-75ch for prose contexts.
- **Label** (JetBrains Mono, 9-11px, weight 600, letter-spacing 0.18-0.20em, uppercase): every chip, every metric-tile label, every nav link, every timestamp, every corner-tag.
- **Mono Numeric** (JetBrains Mono, 11.5px, tabular-nums): journal rows, log rows, scan output, price ticks. Where alignment matters more than style.

### Named Rules

**The Mono-Owns-Chrome Rule.** Every label, chip, button, nav link, section title, page title, brand mark, and metric value is mono. Inter only appears in deliberate prose blocks: hero subhead, modal body, journal note text. If chrome reads as sans-serif, the chrome is wrong.

**The Letter-Spacing-Is-A-Token Rule.** Mono uppercase carries 0.16-0.22em letter-spacing depending on tier (chips 0.18, section titles 0.22, page titles 0.2). The spacing is what makes the type feel HUD; without it, mono uppercase reads as console output, not heads-up display.

**The Tabular-Nums Rule.** Every numeric readout uses `font-variant-numeric: tabular-nums` (declared on `html`/`body` and on `.mono`). Price ticks, scores, latency readouts, percentages: all alignable column-wise without manual padding.

## 4. Elevation

The system is **flat at rest, glowing on state.** No drop shadows on cards or panels in their default state. Depth comes from:

1. Tonal layering: page bg sits under `.panel` gradient, which sits under `.metric-tile`, which sits under chips. Same hue, stepped lightness.
2. Soft edge glow when a panel is `.panel-accent`, using `box-shadow: 0 8px 40px rgba(0,0,0,0.4)` plus a colored 1px outline. Treats the accent as light spilling from the panel.
3. Ambient radial gradients in the tactical background, slowly drifting (`@keyframes glowDrift`, 30s).
4. Backdrop-blur on the modal overlay only; the one earned glassmorphism in the system.

### Shadow Vocabulary

- **Panel Accent Glow** (`box-shadow: 0 0 0 1px color-mix(in oklch, var(--accent) 8%, transparent), 0 8px 40px rgba(0,0,0,0.4)`): only on `.panel-accent`. The screen's operating state spilling from the bordered surface.
- **Orb Glow** (`box-shadow: 0 0 18px var(--accent)` on the 14px core): the pulsing status indicator. Green/amber/red variants.
- **Button Cyan Press** (`box-shadow: 0 4px 0 0 #061e27, 0 0 12px rgba(34,211,238,0.18), inset 0 1px 0 rgba(255,255,255,0.07)`): the 3D-pressable Strike CTA. Compresses to `0 1px 0 0` on `:active`.
- **Modal Lift** (`box-shadow: 0 30px 80px rgba(0,0,0,0.6), 0 0 0 1px color-mix(in oklch, var(--accent) 15%, transparent)`): the one earned heavy shadow, used for modal centering against the blurred backdrop.
- **HUD Text Glow** (`text-shadow: 0 0 6px ..., 0 0 14px ...`): applied to `.hud-glow`, `.hud-glow-amber`, `.hud-glow-red` and to page titles. The CRT bloom; the type is illuminated, not just colored.

### Named Rules

**The Flat-Default Rule.** Panels, cards, chips, buttons, and tiles ship flat. Shadows appear only when state demands it (accent panel, hover, modal, button press). A drop-shadow on a default surface is a bug.

**The Glow-Is-State Rule.** Glow means "this surface is participating in the current operating state." Green glow → engine armed. Amber glow → caution. Red glow → live. Glow is never decorative; if it doesn't reflect state, it doesn't belong.

## 5. Components

### Panels
- **Shape:** 14px radius, 1px `var(--border-soft)` outline.
- **Background:** `linear-gradient(135deg, rgba(0,0,0,0.55), oklch(0.22 0.010 125 / 0.6))`. Gradient anchors top-left.
- **Overlay:** every `.panel` carries a `::before` repeating-linear-gradient scanline at 2px intervals, `rgba(255,255,255,0.012)` opacity. Toggleable via `.scanlines-off`.
- **Accent variant:** `.panel-accent` adds the colored outline + halo glow described under Elevation.
- **Corner brackets:** `.brackets` class adds two 14px corner brackets (top-left, bottom-right) drawn from accent color. Decorative-structural; signals "active panel" without taking up content space.
- **Section header:** internal `.sec-head` divider with `.sec-title` (Share Tech Mono, 13px) and the pulsing accent dot. Separator is `border-bottom: 1px solid var(--border-soft)`.

### Buttons
- **Shape:** 10px radius. Padding 9px 14px.
- **Default (`.btn`):** transparent-ish ghost. Background `rgba(255,255,255,0.03)`, border `var(--border)`, color `var(--fg-2)`, mono uppercase 11.5px, letter-spacing 0.18em, font-weight 800.
- **Variants:** `.btn-red` (live actions), `.btn-orange` (intermediate caution), `.btn-green` (confirm), `.btn-cyan` (primary CTA, 3D-pressable).
- **Cyan CTA:** the standout. Gradient face (`#164e63 → #0e3a4a → #0a2d3a`), 4px bottom shadow as physical depth, inset highlight on the top edge, cyan glow halo. Active state compresses 1px and the bottom shadow halves. This is the one button in the system with weight.
- **Hover:** ghost variants brighten by 3% surface opacity and one fg step. Cyan brightens by `filter: brightness(1.15)`. No transform on hover for ghost variants; Cyan only translates on `:active`.

### Chips
- **Style:** 999px pill, 1px outlined, 10px JetBrains Mono uppercase font, letter-spacing 0.18em. Padding 3px 8px, gap 6px (icon + text).
- **Default:** transparent-tinted background, `var(--fg-2)` text.
- **State variants:** `.chip-accent` (uses dynamic `--accent`), `.chip-green`, `.chip-red`, `.chip-amber`, `.chip-blue`, `.chip-cyan`, `.chip-purple`. Each variant uses an 8-10% tinted background, 30-35% tinted border, and the saturated text color.
- **Used for:** mode tags (STEALTH / STRIKE / SURGICAL / OVERWATCH), state flags (ARMED / LIVE / PAPER), classification (SWING / INTRADAY / SCALP), regime labels.

### Cards / Containers
- **Corner Style:** 12-14px radius depending on tier (panels 14px, metric-tiles 12px, pos cards 12px).
- **Background:** rgba(0,0,0,0.4) or panel-gradient depending on tier.
- **Shadow Strategy:** flat by default, see Elevation.
- **Border:** 1px soft.
- **Internal Padding:** 14-18px depending on density mode (`.density-dense` collapses to 10-12px, `.density-sparse` expands to 18-20px).

### Metric Tile
- **Shape:** 12px radius, 1px `rgba(255,255,255,0.06)` outline.
- **Background:** flat `rgba(0,0,0,0.4)`. Sits on top of `.panel`.
- **Layout:** small uppercase label (top, JetBrains Mono 9.5px, letter-spacing 0.2em), heavy value (Share Tech Mono 26px weight 800), optional sub (JetBrains Mono 10px, letter-spacing 0.12em).
- **Density-aware:** all three values scale via `.density-sparse` / `.density-dense` modifiers on the shell.

### Inputs / Fields
- **Style:** inherited from base. No dedicated `.input` class in the kept system; fields use ghost-button-style outlines when they appear. (The HUD avoids forms wherever possible; inputs that exist are in Settings and inline filters.)
- **Focus:** 2px outline using `var(--accent)`, offset 2px (`outline:2px solid var(--accent); outline-offset:2px`). Used on the hamburger button and adopted across keyboardable affordances.

### Navigation
- **Topbar:** brand mark + nav links + topbar-right cluster (mode badge, Phemex status pill, UTC clock).
- **Nav links:** JetBrains Mono 11px weight 600, uppercase, letter-spacing 0.16em, `var(--fg-3)` at rest. Active link picks up `var(--accent)` text, accent-tinted border and background. Hover lifts to `var(--fg)` with a faint white overlay.
- **Mobile:** ≤700px collapses the nav into a slide-in drawer keyed to the right edge, backdrop-blur darkened. Hamburger appears in the topbar; nav, mode badge, Phemex pill, and UTC clock all move into the drawer.

### Orb (signature component)
- 40px square, contains a 14px solid core, a pinging ring (opacity 0.25, scales to 2.2x over 2.5s), and a blurred halo. Green/amber/red variants matching status. The product's defining live-indicator. Appears in BotStatus, ActiveScanBeacon, and any "is this running?" question the operator might have.

### Reticle (signature component)
- An SVG crosshair scaled to 120% of container, two counter-rotating rings (45s and 30s), opacity 0.18. Sits behind primary content on Scanner and Landing scope panels. Toggleable via `.hud-overlays-off`. Conveys "the system is watching" without competing for attention.

### Tactical Background (signature component)
- A four-layer composition pinned at z-index -10: gradient base, drifting radial glows in the accent color (30s loop), a soft dot grid (40px spacing, drifting 120s), a sweeping scanline (8s sweep), and a fractal-noise grain overlay (0.04 opacity, 0.5s flicker). All four layers respect the dynamic accent; switching modes shifts the entire ambient color of the background.

### HUD Progress Bar (signature component)
- 6px height, gradient from red (left = stop loss) through neutral mid through green (right = take profit). 12px circular marker with accent border and glow, animated `left` transition with `cubic-bezier(0.22, 0.9, 0.3, 1)` over 0.8s. Used on open positions to show price-relative-to-plan in a single glance.

## 6. Do's and Don'ts

### Do:
- **Do** use `var(--accent)` for any element that reflects operating state. The token rebinds per mode (green/amber/red); hard-coded colors are a bug.
- **Do** tint every neutral toward olive. Surfaces sit at chroma 0.008-0.015 on hues 120-150. Pure-gray neutrals read wrong on this palette.
- **Do** reach for chips and labels before reaching for prose. If a status can be a pill, it is a pill.
- **Do** stack monospace fonts by role: Share Tech Mono for display chrome, JetBrains Mono for labels and numerics, Inter only for actual prose.
- **Do** use letter-spacing 0.16-0.22em on every mono uppercase string. The spacing is structural, not cosmetic.
- **Do** keep panels flat at rest. Glow only on `.panel-accent` and live-state surfaces.
- **Do** put the accent dot on every `.sec-title`. The pulsing dot signals the panel is participating in the current state.
- **Do** capitalize mode labels and signal tags (STEALTH, ARMED, FIRED, REJECTED). Lowercase chrome reads as a SaaS dashboard.
- **Do** include a `density-sparse` / `density-dense` modifier path on any new tile or row component.

### Don't:
- **Don't** use `#000` or `#fff`. Every neutral is olive-tinted OKLCH. Pure-black backgrounds are forbidden.
- **Don't** use Inter for chrome (labels, buttons, chips, page titles, section titles, metric values). Inter is for prose only.
- **Don't** use em dashes in UI copy. Use commas, colons, semicolons, periods, or parentheses. Two hyphens (`--`) is also banned.
- **Don't** use purple-to-blue gradients, especially on hero metrics or CTAs. This is the SaaS-template reflex the system explicitly rejects.
- **Don't** stack cards inside cards. A panel may contain metric-tiles or pos cards, but a `.metric-tile` inside a `.metric-tile` inside a `.panel` is wrong.
- **Don't** use side-stripe borders. No `border-left: 4px solid <color>` as a status accent. Use a corner-tag, a chip, full-border + tint, or the panel-accent glow.
- **Don't** use bounce or elastic easing. Animations use exponential ease-out (the marker transition uses `cubic-bezier(0.22, 0.9, 0.3, 1)`; the glow loops are simple `ease-in-out`). No `cubic-bezier` with overshoot.
- **Don't** drop-shadow surfaces by default. Shadows are state, not decoration. Glassmorphism (`backdrop-filter: blur(...)`) is allowed only on the modal backdrop, where the blur serves z-layering.
- **Don't** animate layout properties (width, height, top, left, padding, margin). Animate transforms and opacity. The marker bar animates `left`, which is the one tolerated exception, and only because the bar is purely decorative geometry, not layout.
- **Don't** use illustrated empty states, soft pastels, "Welcome back!" copy, or any consumer-finance softness. The empty state for a scan with no candidates is a chip that says `NO CANDIDATES` and a one-line reason, not a friendly illustration.
- **Don't** introduce a hero-metric template (big number + tiny label + supporting stat + gradient accent). That's the AI-tool landing reflex; product surfaces don't get it, and landing has its own register-specific hero treatment.
- **Don't** modify `min_confluence_score` or pre-scoring gate thresholds in the name of "better defaults." The numbers were tuned from session win-rate data and live outside the design system's jurisdiction.
