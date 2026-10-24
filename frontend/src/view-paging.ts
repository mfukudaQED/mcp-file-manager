// Keep initial loading automatic; further page loading requires the Load more button.
export const INITIAL_VIEW_LINES = 1000;
export const VIEW_PAGE_LINES = 1000;

export function needsInitialFill(nextLine: number): boolean {
  return Number.isSafeInteger(nextLine) && nextLine > 0 && nextLine <= INITIAL_VIEW_LINES;
}
