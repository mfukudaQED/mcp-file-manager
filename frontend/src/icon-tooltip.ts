/** Floating help labels for icon-only controls, even inside scrollable panes. */
export interface BoxRect {
  left: number;
  top: number;
  right: number;
  bottom: number;
  width: number;
  height: number;
}

export function tooltipPosition(
  anchor: BoxRect,
  tooltipWidth: number,
  tooltipHeight: number,
  viewportWidth: number,
  viewportHeight: number,
): { left: number; top: number } {
  const margin = 8;
  const offset = 8;
  const width = Math.max(0, tooltipWidth);
  const height = Math.max(0, tooltipHeight);
  const left = Math.max(margin, Math.min(
    anchor.left + anchor.width / 2 - width / 2,
    Math.max(margin, viewportWidth - width - margin),
  ));
  const above = anchor.top - height - offset;
  const below = anchor.bottom + offset;
  const top = above >= margin || below + height > viewportHeight - margin
    ? Math.max(margin, above)
    : below;
  return { left, top };
}

export function installIconTooltips(): void {
  const tooltipElement = document.getElementById("icon-tooltip");
  if (!tooltipElement) throw new Error("Missing icon tooltip element");
  const tooltip: HTMLElement = tooltipElement;
  let owner: HTMLElement | null = null;
  let previousTitle: string | null = null;

  function dismiss(): void {
    tooltip.hidden = true;
    if (owner && previousTitle !== null && !owner.hasAttribute("title")) {
      owner.setAttribute("title", previousTitle);
    }
    owner = null;
    previousTitle = null;
  }

  function nearestIconButton(target: EventTarget | null): HTMLElement | null {
    if (!(target instanceof Element)) return null;
    const button = target.closest<HTMLElement>(".icon-btn, .twisty, .close-tab");
    if (!button || button.closest("[hidden]") ||
        button.getAttribute("aria-hidden") === "true") {
      return null;
    }
    return button;
  }

  function display(button: HTMLElement): void {
    if (owner === button && !tooltip.hidden) return;
    dismiss();
    const description = button.getAttribute("aria-label") || button.getAttribute("title");
    if (!description) return;
    owner = button;
    previousTitle = button.getAttribute("title");
    // Avoid competing native browser tooltips while the custom label is shown.
    if (previousTitle !== null) button.removeAttribute("title");
    tooltip.textContent = description;
    tooltip.hidden = false;
    const bounds = button.getBoundingClientRect();
    const tipBounds = tooltip.getBoundingClientRect();
    const pos = tooltipPosition(bounds, tipBounds.width, tipBounds.height,
      document.documentElement.clientWidth, document.documentElement.clientHeight);
    tooltip.style.left = pos.left + "px";
    tooltip.style.top = pos.top + "px";
  }

  document.addEventListener("pointerover", (event: PointerEvent) => {
    if (event.pointerType === "touch") return;
    const button = nearestIconButton(event.target);
    if (button) display(button);
  });
  // Some browsers do not dispatch pointerover on disabled buttons. Resolve the
  // actual element under the cursor so disabled icon meanings remain discoverable.
  document.addEventListener("pointermove", (event: PointerEvent) => {
    if (event.pointerType === "touch") return;
    const hovered = nearestIconButton(document.elementFromPoint(event.clientX, event.clientY));
    if (hovered) display(hovered);
    else if (owner && !owner.matches(":focus-visible")) dismiss();
  }, { passive: true });
  document.addEventListener("pointerout", (event: PointerEvent) => {
    if (!owner || !owner.contains(event.target as Node)) return;
    if (event.relatedTarget instanceof Node && owner.contains(event.relatedTarget)) return;
    dismiss();
  });
  document.addEventListener("focusin", (event: FocusEvent) => {
    const button = nearestIconButton(event.target);
    if (button) display(button);
  });
  document.addEventListener("focusout", (event: FocusEvent) => {
    if (owner && event.target instanceof Node && owner.contains(event.target)) dismiss();
  });
  document.addEventListener("pointerdown", dismiss, true);
  document.addEventListener("scroll", dismiss, true);
  document.addEventListener("keydown", (event: KeyboardEvent) => {
    if (event.key === "Escape") dismiss();
  });
  window.addEventListener("resize", dismiss);
}
