---
name: SniperSight
description: Quiet, high-density trading terminal for evidence-led decisions
colors:
  bg: "#0b0e11"
  bg-2: "#101316"
  card: "#12161a"
  card-2: "#171c21"
  border: "rgba(255,255,255,0.12)"
  border-soft: "rgba(255,255,255,0.065)"
  fg: "#f2f4f7"
  fg-2: "#c9d0d8"
  fg-3: "#98a2b3"
  fg-4: "#7f8998"
  green: "#2ce56b"
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
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(38px, 5.4vw, 68px)"
    fontWeight: 400
    lineHeight: "0.98"
    letterSpacing: "0.01em"
  page-title:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: "1.08"
    letterSpacing: "-0.025em"
  section-title:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  metric-value:
    fontFamily: "'JetBrains Mono', monospace"
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
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "10px"
    fontWeight: 600
    letterSpacing: "0.04em"
  mono:
    fontFamily: "'JetBrains Mono', monospace"
    fontSize: "11.5px"
    fontWeight: 400
    fontFeature: "tabular-nums"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "8px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "18px"
  xl: "24px"
  shell-x: "24px"
components:
  panel:
    backgroundColor: "#12161a"
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

**Creative North Star: "The Quiet Trading Terminal"**

SniperSight is a dense decision surface for a working trader. The reference is the calm hierarchy of a modern exchange terminal: dark neutral grounds, thin dividers, compact controls, clear rows, and one strong action colour. Light mode is not on the roadmap.

Interface chrome uses Inter so labels keep normal word shapes at small sizes. JetBrains Mono is reserved for prices, quantities, timestamps, compact status codes, and other values that benefit from aligned characters. Colour remains semantic: green for positive/action, amber for caution or paper exposure, and red for danger or live exposure.

The system rejects decorative scanlines, glowing card walls, large radii, stacked gradients, and wide-tracked uppercase prose. Density comes from alignment and spacing, not from shrinking text or boxing every group.

**Key Characteristics:**
- Neutral dark surfaces with one raised level and one quiet divider
- Inter for interface chrome; JetBrains Mono for aligned market data
- Accent color is dynamic: green by default, amber for warnings, red for live mode
- Flat panels with 4–8px radii and no decorative overlays
- High density, low ornamentation; every chip and border is structural

## 2. Colors: The Neutral Terminal Palette

The system runs on near-black neutrals plus a status-coded accent family. Strategy is **restrained at rest, committed under state**. Saturated colour enters through actions, thin edges, price direction, and status chips.

### Primary
- **Action Green** (`#2ce56b`): the default accent for positive direction and primary action.

### Secondary
- **Live Mode Red** (`#ff6464` / softer `#f87171`): the live-trading state, danger affordances, sell-side direction, breach indicators. Page titles switch to red when bot mode is live. Used in `.btn-red`, `.chip-red`, `.hud-glow-red`.

### Tertiary
- **Warning Amber** (`#ffc266` / `#fbbf24`): the page-title default tone, warning chips, paper-mode demarcation, regime-cautious states. The non-live, non-success middle band.
- **Strike Cyan** (`#22d3ee`): the Strike-mode accent and the primary CTA pressable. `.btn-cyan` is the only 3D-pressable button in the system. Used sparingly.

### Neutral
- **Surface Deep** (`#0b0e11`): page background.
- **Surface Mid** (`#101316`): persistent chrome.
- **Surface Card** (`#12161a`): raised panels.
- **Surface Card Hover** (`#171c21`): hover and selected rows.
- **Border** (`rgba(255,255,255,.12)`): control outlines.
- **Border Soft** (`rgba(255,255,255,.065)`): dividers and panel edges.
- **FG Primary** (`#f2f4f7`): primary text and metrics.
- **FG Secondary** (`#c9d0d8`): body prose and button text.
- **FG Tertiary** (`#98a2b3`): navigation and supporting copy.
- **FG Quaternary** (`#7f8998`): labels and timestamps.

### Named Rules

**The Near-Black Rule.** The app background is `#0b0e11`; raised surfaces step upward just enough for dividers and alignment to define structure.

**The Dynamic Accent Rule.** The `--accent` token is whatever the current state mandates: green at rest, amber on warning surfaces, red in live mode. Every chip, button, panel-edge, and orb that wants the operating-state color references `var(--accent)`, not a hard-coded hue. Hard-coding green into a status-aware surface is a bug.

**The 10% Saturation Rule.** Saturated colors cover ≤10% of any single screen. Green actions, red risk, amber warnings, and cyan stock-workspace cues are used in pixels, not percentages. The remaining 90% is neutral.

## 3. Typography

**Display/UI Font:** `Inter` (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Body Font:** `Inter` (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Label/Mono Font:** `JetBrains Mono` (with `monospace` fallback)

**Character:** Inter owns navigation, headings, buttons, forms, and prose. JetBrains Mono carries numbers and compact machine evidence where fixed-width alignment improves scanning. Uppercase is reserved for genuine status codes, not ordinary interface labels or sentences.

### Hierarchy
- **Display** (Inter, `clamp(38px, 5.4vw, 68px)`, weight 600): used sparingly on the market chooser and stock training hero.
- **Page Title** (Inter, 32px, weight 600, line-height 1.08, letter-spacing -0.025em): the route heading.
- **Section Title** (Inter, 14px, weight 600): panel headers in normal title case.
- **Metric Value** (JetBrains Mono, 26px, weight 600, tabular numerals): the prominent number on a metric tile.
- **Body** (Inter, 14px, weight 400, line-height 1.55): prose, forms, navigation, and controls.
- **Label** (Inter, 11px, weight 600): compact interface labels; uppercase only when the value is a code or state.
- **Mono Numeric** (JetBrains Mono, 11.5px, tabular-nums): journal rows, log rows, scan output, price ticks. Where alignment matters more than style.

### Named Rules

**The Sans-Owns-Chrome Rule.** If a string is navigation, a heading, a button, a form label, or prose, it uses Inter. Mono is evidence, not atmosphere.

**The Normal-Word-Shape Rule.** Ordinary labels use normal case and restrained tracking. Wide-spaced uppercase is limited to short machine states where the capitalization carries meaning.

**The Tabular-Nums Rule.** Every numeric readout uses `font-variant-numeric: tabular-nums` (declared on `html`/`body` and on `.mono`). Price ticks, scores, latency readouts, percentages: all alignable column-wise without manual padding.

## 4. Elevation

The system is **flat at rest and explicit under state.** Depth comes from three neutral surface levels and thin dividers. A state may change an edge, chip, value, or action face; it does not add decorative elevation.

### Shadow Vocabulary

- **Default surfaces:** no shadow.
- **Sheets and modals:** one directional shadow only when the layer genuinely sits above live content.
- **Focus:** a clear outline, never a glow substituted for keyboard visibility.

### Named Rules

**The Flat-Default Rule.** Panels, cards, chips, buttons, and tiles ship flat. Shadows appear only when state demands it (accent panel, hover, modal, button press). A drop-shadow on a default surface is a bug.

**The Edge-Is-State Rule.** State belongs on a thin edge, chip, value, or action face. It must not tint or illuminate an entire neutral work surface.

## 5. Components

### Panels
- **Shape:** 8px radius, 1px `var(--border-soft)` outline.
- **Background:** flat `var(--card)`.
- **Overlay:** none. Texture never competes with chart data or form labels.
- **Accent variant:** `.panel-accent` changes the edge colour without adding a glow.
- **Section header:** Inter 14px/600 over one quiet divider.

### Buttons
- **Shape:** 6px radius. Minimum height 36px desktop and 44px touch. Padding 8px 14px.
- **Default (`.btn`):** restrained ghost control using Inter 12.5px/600 in normal case.
- **Variants:** `.btn-red` (live actions), `.btn-orange` (intermediate caution), `.btn-green` (confirm), `.btn-cyan` (primary CTA, 3D-pressable).
- **Primary CTA:** a solid `var(--accent)` face with dark text and no glow or raised shadow.
- **Hover:** brighten or darken the existing face without moving the control.

### Chips
- **Style:** 999px pill, 11px Inter/600, restrained tracking. Padding 3px 8px.
- **Default:** transparent-tinted background, `var(--fg-2)` text.
- **State variants:** `.chip-accent` (uses dynamic `--accent`), `.chip-green`, `.chip-red`, `.chip-amber`, `.chip-blue`, `.chip-cyan`, `.chip-purple`. Each variant uses an 8-10% tinted background, 30-35% tinted border, and the saturated text color.
- **Used for:** mode tags (STEALTH / STRIKE / SURGICAL / OVERWATCH), state flags (ARMED / LIVE / PAPER), classification (SWING / INTRADAY / SCALP), regime labels.

### Cards / Containers
- **Corner Style:** 4–8px depending on tier.
- **Background:** one of the two neutral surface levels.
- **Shadow Strategy:** flat by default, see Elevation.
- **Border:** 1px soft.
- **Internal Padding:** 14-18px depending on density mode (`.density-dense` collapses to 10-12px, `.density-sparse` expands to 18-20px).

### Metric Tile
- **Shape:** 8px radius, 1px `var(--border-soft)` outline.
- **Background:** flat `var(--card)`.
- **Layout:** small sans label, aligned JetBrains Mono value, optional mono subline.
- **Density-aware:** all three values scale via `.density-sparse` / `.density-dense` modifiers on the shell.

### Inputs / Fields
- **Style:** inherited from base. No dedicated `.input` class in the kept system; fields use ghost-button-style outlines when they appear. (The HUD avoids forms wherever possible; inputs that exist are in Settings and inline filters.)
- **Focus:** 2px outline using `var(--accent)`, offset 2px (`outline:2px solid var(--accent); outline-offset:2px`). Used on the hamburger button and adopted across keyboardable affordances.

### Navigation
- **Topbar:** brand mark + nav links + topbar-right cluster (mode badge, Phemex status pill, UTC clock).
- **Nav links:** Inter 12.5px weight 500, normal case, `var(--fg-3)` at rest. Active links use primary text, a neutral raised surface, and a thin accent edge.
- **Mobile:** ≤700px collapses the nav into a slide-in drawer keyed to the right edge, backdrop-blur darkened. Hamburger appears in the topbar; nav, mode badge, Phemex pill, and UTC clock all move into the drawer.

### Orb (signature component)
- 40px square, contains a 14px solid core, a pinging ring (opacity 0.25, scales to 2.2x over 2.5s), and a blurred halo. Green/amber/red variants matching status. The product's defining live-indicator. Appears in BotStatus, ActiveScanBeacon, and any "is this running?" question the operator might have.

### Reticle (signature component)
- An SVG crosshair scaled to 120% of container, two counter-rotating rings (45s and 30s), opacity 0.18. Sits behind primary content on Scanner and Landing scope panels. Toggleable via `.hud-overlays-off`. Conveys "the system is watching" without competing for attention.

### Background
- A single neutral app ground. No grid, scanline, grain, or decorative light effect sits behind working data.

### HUD Progress Bar (signature component)
- 6px height, gradient from red (left = stop loss) through neutral mid through green (right = take profit). 12px circular marker with accent border and glow, animated `left` transition with `cubic-bezier(0.22, 0.9, 0.3, 1)` over 0.8s. Used on open positions to show price-relative-to-plan in a single glance.

## 6. Do's and Don'ts

### Do:
- **Do** use `var(--accent)` for any element that reflects operating state. The token rebinds per mode (green/amber/red); hard-coded colors are a bug.
- **Do** use the neutral surface ladder and thin dividers before adding another container.
- **Do** use Inter for navigation, headings, buttons, forms, and prose.
- **Do** reserve JetBrains Mono for prices, quantities, timestamps, aligned statistics, and compact machine states.
- **Do** keep panels flat and use colour only when it communicates action, direction, or risk.
- **Do** capitalize genuine mode labels and signal codes (ARMED, FIRED, REJECTED), while keeping ordinary interface labels in normal case.
- **Do** include a `density-sparse` / `density-dense` modifier path on any new tile or row component.

### Don't:
- **Don't** use pure `#000` or `#fff`; the neutral ladder carries the visual hierarchy.
- **Don't** use decorative mono, scanlines, corner brackets, glow, or wide-tracked uppercase as atmosphere.
- **Don't** use em dashes in UI copy. Use commas, colons, semicolons, periods, or parentheses. Two hyphens (`--`) is also banned.
- **Don't** use purple-to-blue gradients, especially on hero metrics or CTAs. This is the SaaS-template reflex the system explicitly rejects.
- **Don't** stack cards inside cards. A panel may contain metric-tiles or pos cards, but a `.metric-tile` inside a `.metric-tile` inside a `.panel` is wrong.
- **Don't** use thick side-stripe borders. Prefer a 1–2px active edge, a chip, or a single semantic value colour.
- **Don't** use bounce or elastic easing. Animations use exponential ease-out; the marker transition uses `cubic-bezier(0.22, 0.9, 0.3, 1)`. No `cubic-bezier` with overshoot.
- **Don't** drop-shadow surfaces by default. Shadows are state, not decoration. Glassmorphism (`backdrop-filter: blur(...)`) is allowed only on the modal backdrop, where the blur serves z-layering.
- **Don't** animate layout properties (width, height, top, left, padding, margin). Animate transforms and opacity. The marker bar animates `left`, which is the one tolerated exception, and only because the bar is purely decorative geometry, not layout.
- **Don't** use illustrated empty states, soft pastels, "Welcome back!" copy, or any consumer-finance softness. The empty state for a scan with no candidates is a chip that says `NO CANDIDATES` and a one-line reason, not a friendly illustration.
- **Don't** introduce a hero-metric template (big number + tiny label + supporting stat + gradient accent). That's the AI-tool landing reflex; product surfaces don't get it, and landing has its own register-specific hero treatment.
- **Don't** modify `min_confluence_score` or pre-scoring gate thresholds in the name of "better defaults." The numbers were tuned from session win-rate data and live outside the design system's jurisdiction.
