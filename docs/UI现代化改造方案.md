# KIVO Modern UI Redesign — Phase 1 Baseline

> Branch: ui/modern-redesign-phase1  
> Scope: staged UI refinement, preserving the existing Tkinter/Pillow core and current feature behavior.

## Design direction
- Product identity: KIVO / 启沃 — modern, restrained, professional desktop productivity utility.
- Visual approach: Windows Fluent-inspired, clean surfaces, subtle borders, restrained blue accent; avoid heavy animation and visual clutter.
- Primary accent: #3B82F6. Secondary accent: #8B5CF6.
- Light theme baseline: window #F3F6FB, cards #FFFFFF, primary text #1C2634, muted text #64748B, border #E5EAF0.
- Dark theme is a later implementation milestone; do not claim support until all custom Tk widgets, dialogs, overlays and image surfaces are tested.
- Iconography: consistent line icons; avoid emoji icons in controls.
- Typography: Microsoft YaHei UI on Windows; robust platform fallback.
- Accessibility: visible focus, adequate contrast, keyboard navigation, DPI-aware layout.

## Main window layout
- Keep the existing feature/navigation structure and clipboard queue as the core screen.
- Sidebar: brand header, navigation items grouped consistently, settings and version pinned to the bottom. Future milestone: collapsible sidebar.
- Content: page title and context line; feature-specific workspace; status feedback at bottom.
- Home/clipboard workspace: records list is the dominant area; action buttons grouped and ordered by primary action; settings sections are progressively disclosed rather than crowded.
- Target default window: 1200x760 where feasible; retain adaptive sizing and do not impose a fixed size that clips controls. Test minimum-size and DPI behavior before changing.

## Page standards
### AI assistant
- Conversation history/search/new chat in a left panel.
- Chat workspace with model/connection status, message content, input box and attachment/stop/retry controls.
- Protect secrets; mask keys and redact logs. No API key in diagnostic exports.
### OCR
- Split workspace: image preview and recognized/editable text.
- Actions: copy, translate, AI processing and export; progress/errors clearly shown.
### Screenshot editor
- Compact floating toolbar; tools grouped logically; color/width controls; undo/redo; clear distinction between copy and save.
- Keep capture latency and overlay behavior as priority over decorative styling.
### Translation
- Source and target panes, language swap, copy, clear and history.
### Settings
- Category navigation with a focused content panel; grouping, explanatory text, validation and immediate-save feedback.
- Keep advanced options collapsed by default where appropriate.

## Implementation sequence
1. Build reusable UI tokens and components; validate across current widgets and dialogs.
2. Refine sidebar/navigation and main workspace layout without changing business logic.
3. Refine AI chat panel.
4. Refine settings.
5. Refine OCR, translation and screenshot surfaces individually.
6. Add theme preference and DPI/layout tests only after coverage is adequate.

## Safety/compatibility guardrails
- Do not rewrite the entire app or migrate frameworks in this phase.
- Do not remove or rename user settings without migration.
- Keep core hotkeys, clipboard operations, screenshot capture, OCR, AI requests, downloads, backup and updater behavior intact.
- Each implementation increment must have tests and a reviewable commit; Windows UI validation remains necessary.
