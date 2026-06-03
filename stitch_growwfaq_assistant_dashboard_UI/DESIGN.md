---
name: Obsidian Emerald
colors:
  surface: '#051424'
  surface-dim: '#051424'
  surface-bright: '#2c3a4c'
  surface-container-lowest: '#010f1f'
  surface-container-low: '#0d1c2d'
  surface-container: '#122131'
  surface-container-high: '#1c2b3c'
  surface-container-highest: '#273647'
  on-surface: '#d4e4fa'
  on-surface-variant: '#bacac1'
  inverse-surface: '#d4e4fa'
  inverse-on-surface: '#233143'
  outline: '#85948c'
  outline-variant: '#3c4a43'
  surface-tint: '#2fe0aa'
  primary: '#44edb7'
  on-primary: '#003828'
  primary-container: '#00d09c'
  on-primary-container: '#00533c'
  inverse-primary: '#006c4f'
  secondary: '#c3c6d4'
  on-secondary: '#2c303b'
  secondary-container: '#454955'
  on-secondary-container: '#b5b8c6'
  tertiary: '#c8d4ec'
  on-tertiary: '#263143'
  tertiary-container: '#adb8cf'
  on-tertiary-container: '#3e495c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#59fdc5'
  primary-fixed-dim: '#2fe0aa'
  on-primary-fixed: '#002116'
  on-primary-fixed-variant: '#00513b'
  secondary-fixed: '#dfe2f1'
  secondary-fixed-dim: '#c3c6d4'
  on-secondary-fixed: '#171b26'
  on-secondary-fixed-variant: '#434652'
  tertiary-fixed: '#d8e3fb'
  tertiary-fixed-dim: '#bcc7de'
  on-tertiary-fixed: '#111c2d'
  on-tertiary-fixed-variant: '#3c475a'
  background: '#051424'
  on-background: '#d4e4fa'
  surface-variant: '#273647'
typography:
  display-lg:
    fontFamily: Outfit
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Outfit
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
---

## Brand & Style

The design system is engineered for a premium fintech experience, specifically tailored for mutual fund assistance. It balances the high-trust requirements of financial services with a cutting-edge, modern aesthetic. The brand personality is precise, forward-thinking, and reassuring.

The visual style utilizes **Modern Glassmorphism** mixed with **Minimalism**. It creates depth through translucent layers and backdrop blurs rather than traditional heavy shadows. The UI should evoke a sense of digital "transparency" and sophistication, using the high-contrast green to signal growth and action against a deep, focused obsidian backdrop.

## Colors

The palette is anchored by **Groww Green (#00D09C)**, used exclusively for primary actions, success states, and growth indicators. 

The background strategy employs a "layered dark" approach. **Deep Obsidian** serves as the base canvas, while **Sleek Slate** and **Translucent Glass** define interactive surfaces and containers. For light-mode contexts or specific document-heavy views, **Soft Gray** provides a clean, breathable alternative.

**Compliance & Guardrails:** Use Warm Amber and Coral sparingly to highlight regulatory warnings or critical errors, ensuring they contrast sharply against the dark surfaces without overwhelming the primary brand color.

## Typography

This design system uses a dual-font strategy. **Outfit** is used for headings and display text to provide a modern, geometric character that feels premium and tech-forward. **Inter** is used for all body copy and UI labels to ensure maximum legibility and functional clarity in data-dense financial views.

Maintain a strict weight hierarchy: 
- Use **Semibold (600)** for primary titles to anchor the page.
- Use **Medium (500)** for secondary headers.
- Use **Regular (400)** for all long-form reading and mutual fund descriptions.

## Layout & Spacing

The layout follows a **Fluid Grid** model with a 12-column structure for desktop and a 4-column structure for mobile. 

- **Spacing Rhythm:** Built on a 4px base unit. Component internal padding should favor 16px (sm) or 24px (md) to maintain a spacious, premium feel.
- **Desktop:** Max-width of 1440px with centered alignment.
- **Margins:** Use 48px margins on desktop to create a "contained" feel that mirrors high-end SaaS dashboards. 
- **Reflow:** On mobile, glass cards should span the full width of the screen minus the 16px side margins.

## Elevation & Depth

Depth is established through **Backdrop Blurs** and **Tonal Layering** rather than traditional black shadows.

1.  **Level 0 (Base):** Deep Obsidian (#0B0F19) - The furthest background layer.
2.  **Level 1 (Cards):** Translucent Glass (rgba(30, 41, 59, 0.7)) with a `backdrop-filter: blur(12px)`.
3.  **Level 2 (Modals/Popovers):** Sleek Slate (#1E293B) with a subtle 1px "glowing" border: `1px solid rgba(255, 255, 255, 0.08)`.

Shadows should be "Ambient" - very soft, using a 15% opacity of the primary background color with a large 30px spread for high-elevation elements like floating action buttons.

## Shapes

The shape language is consistently **Rounded**, reflecting a friendly yet professional fintech persona. 

- **Standard Containers:** Use 12px corners for inputs and small cards.
- **Main Sections:** Use 16px corners for large content blocks and glass containers.
- **Interactive Elements:** Buttons should use 12px or a full "Pill" shape depending on the context (use Pill for tags/chips, 12px for primary actions).

## Components

- **Buttons:** Primary buttons use a solid Groww Green fill with Deep Charcoal text. Secondary buttons use a glass background with a 1px white-alpha border.
- **Input Fields:** Semi-transparent dark fills. On focus, the border transitions to Groww Green with a subtle outer glow (0px 0px 8px rgba(0, 208, 156, 0.3)).
- **Glass Cards:** Always include a 1px top-weighted border to simulate a light source from above. 
- **Pulsing Status Indicators:** For "Live" fund data or system status, use a 8px circle of Groww Green with a 50% opacity concentric ring that pulses outward.
- **Chips:** Small, pill-shaped markers for fund categories (e.g., "Equity", "Debt"). Use Sleek Slate backgrounds with White labels.
- **Lists:** Transaction lists should have no visible borders between items; use subtle 8px vertical spacing and distinct glass backgrounds for each row to imply separation.