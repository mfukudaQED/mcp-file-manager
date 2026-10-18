import { App } from "@modelcontextprotocol/ext-apps";
import { Vim } from "@replit/codemirror-vim";
import { CodeEditor, type KeymapMode } from "./code-editor";
import { DiffView } from "./diff-view";
import { readCompleteRevision, type CompleteRevision } from "./revision-reader";
import { findMatches, MAX_TABS, type Match } from "./search";
import {
  childPath, decodeToolResult, nextCursor, parentDirectory,
  type Cursor, type JsonRecord,
} from "./state";
import {
  languageFor, MAX_DOCUMENT_CHARS, MAX_PREVIEW_CHARS,
  renderMarkdown, renderSource,
} from "./presentation";

const app = new App({ name: "MCP File Manager", version: "0.1.0" });
const el = (id: string): HTMLElement => document.getElementById(id)!;
const input = (): HTMLInputElement => el("path") as HTMLInputElement;

// The explorer starts collapsed to leave the entire panel width for text.
// Its state is local to this MCP App view and never changes editor contents.
function setExplorerOpen(open: boolean): void {
  const sidebar = el("explorer-panel");
  const toggle = el("explorer-toggle") as HTMLButtonElement;
  sidebar.hidden = !open;
  el("workspace").classList.toggle("explorer-open", open);
  toggle.setAttribute("aria-expanded", String(open));
  toggle.textContent = open ? "◂ Hide Explorer" : "☰ Explorer";
  toggle.title = open ? "Hide File Explorer" : "Show File Explorer";
}

function toggleExplorer(): void {
  const open = el("explorer-panel").hidden;
  setExplorerOpen(open);
  if (open && active) {
    const directory = parentDirectory(active.path);
    if (directory !== currentDirectory) {
      void operation(async () => {
        status("Loading folder…");
        rootTree(await tool("file_viewer_list", { path: directory, limit: 70 }));
        status("Folder opened");
      });
    }
  }
}

interface OpenedFile {
  path: string;
  revision: string;
  totalLines: number;
  sizeBytes: number;
  kind: "markdown" | "text";
}

interface FileEntry {
  name: string;
  type: string;
}

interface OutlineHeading {
  id: string;
  title: string;
  level: number;
  start_line: number;
}

type ViewMode = "source" | "preview";
let connected = false;
let busy = false;
let active: OpenedFile | null = null;
let currentText = "";
let currentDirectory: string | null = null;
let continuation: Cursor | null = null;
let queuedHostPath: string | null = null;
type LogWindow = {
  path: string; revision: string; identity: string; size_bytes: number;
  content: string; start_byte: number; end_byte: number;
  has_earlier: boolean; has_later: boolean;
};
let logWindow: LogWindow | null = null;

let viewMode: ViewMode = "source";
let editing = false;
let originalText = "";
let editRevision = "";
let editDirty = false;
let codeEditor: CodeEditor | null = null;
let diffViewer: DiffView | null = null;
let gitPreview: DiffView | null = null;
let selectedCommitId = "";
let selectedGitRevision = "";
let selectedCurrentRevision = "";
let selectedHistoryPath = "";
let historyVisible = false;
let keymapMode: KeymapMode = "standard";
const EDIT_LIMIT = 64 * 1024;
function confirmDiscard(): boolean {
  return !editing || !editDirty ||
    window.confirm("Discard unsaved edits? Your changes will be lost.");
}
function resetEditor(): void {
  editing = false; editDirty = false; originalText = ""; editRevision = "";
  closeDiff();
  codeEditor?.destroy(); codeEditor = null;
  el("editor-pane").replaceChildren(); el("editor-pane").hidden = true;
}
function closeDiff(): void {
  diffViewer?.destroy();
  diffViewer = null;
  el("diff-panel").hidden = true;
  el("diff-content").replaceChildren();
}
function closeHistory(): void {
  gitPreview?.destroy();
  gitPreview = null;
  historyVisible = false;
  selectedCommitId = "";
  selectedGitRevision = "";
  selectedCurrentRevision = "";
  selectedHistoryPath = "";
  el("history-panel").hidden = true;
  el("history-items").replaceChildren();
  el("history-detail").replaceChildren();
}
function renderPreview(
  content: string, backupId: string, revision: string,
  currentContent: string, currentRevision: string, path: string,
): void {
  selectedCommitId = backupId;
  selectedGitRevision = revision;
  selectedCurrentRevision = currentRevision;
  selectedHistoryPath = path;
  const pane = el("history-detail");
  gitPreview?.destroy();
  gitPreview = null;
  pane.replaceChildren();
  const message = document.createElement("p");
  message.textContent = "Compare the selected Git commit before restoring its file.";
  pane.append(message);
  const comparison = document.createElement("div");
  pane.append(comparison);
  gitPreview = new DiffView(comparison, path, content, currentContent);
  const restore = document.createElement("button");
  restore.textContent = "Restore this commit";
  // This is created inside an operation (busy=true); the button is for later clicks.
  restore.disabled = !connected;
  restore.addEventListener("click", () => {
    void restoreBackup();
  });
  const close = document.createElement("button");
  close.textContent = "Close preview";
  close.addEventListener("click", () => {
    gitPreview?.destroy();
    gitPreview = null;
    pane.replaceChildren();
    selectedCommitId = "";
    selectedGitRevision = "";
    selectedCurrentRevision = "";
    selectedHistoryPath = "";
  });
  pane.append(restore, close);
}
async function readGitContent(path: string, commit: string): Promise<CompleteRevision> {
  return readCompleteRevision(
    (offset, revision) => tool("file_manager_git_read", {
      path, commit, offset, revision, max_chars: 5000,
    }),
  );
}
async function readCurrentFull(file: OpenedFile): Promise<CompleteRevision> {
  if (file.sizeBytes > EDIT_LIMIT) throw new Error("Full diff is limited to 64 KiB files.");
  return readCompleteRevision(
    (offset, revision) => tool("file_manager_edit_read", {
      path: file.path, offset, revision, max_chars: 7000,
    }),
    file.revision,
  );
}
async function openHistory(): Promise<void> {
  if (busy || !active || editing || logWindow || active.sizeBytes > EDIT_LIMIT) return;
  if (historyVisible) { closeHistory(); return; }
  await operation(async () => {
    const file = active!;
    const data = await tool("file_manager_git_history", {path: file.path});
    if (!Array.isArray(data.commits) || typeof data.managed !== "boolean")
      throw new Error("Invalid Git history");
    closeHistory();
    historyVisible = true;
    el("history-panel").hidden = false;
    const list = el("history-items");
    const title = document.createElement("strong");
    title.textContent = "Git commit history";
    list.append(title);
    if (!data.commits.length) {
      const empty = document.createElement("p");
      empty.textContent = data.managed ? "No commits for this file." : "This file is not tracked by Git. You can still edit and save it.";
      list.append(empty);
    }
    for (const entry of data.commits) {
      if (!entry || typeof entry.id !== "string" || typeof entry.date !== "string") continue;
      const row = document.createElement("div");
      row.className = "history-row";
      const button = document.createElement("button");
      button.textContent = "Compare";
      const time = document.createElement("span");
      time.textContent = entry.date + " · " + String(entry.subject || "").slice(0, 180);
      button.addEventListener("click", () => void operation(async () => {
        status("Reading complete revision-pinned contents for comparison…");
        const current = await readCurrentFull(file);
        const result = await readGitContent(file.path, entry.id);
        if (active?.path !== file.path || active.revision !== current.revision) {
          throw new Error("Selected file changed; reopen its history.");
        }
        renderPreview(result.text, entry.id, result.revision,
          current.text, current.revision, file.path);
        status("Complete Git diff loaded; restoration requires confirmation.");
      }));
      row.append(button, time);
      list.append(row);
    }
    status("Git history loaded");
  });
}
async function restoreBackup(): Promise<void> {
  if (busy || !active || !selectedCommitId || !selectedGitRevision ||
      !selectedCurrentRevision || !selectedHistoryPath || editing) return;
  if (active.path !== selectedHistoryPath || active.revision !== selectedCurrentRevision) {
    status("File selection changed. Reopen History before restoring.", true);
    return;
  }
  if (!window.confirm("Replace the current file with this Git revision? Uncommitted changes will be lost. No automatic commit or backup is created.")) return;
  const path = selectedHistoryPath;
  const id = selectedCommitId;
  const expectedRevision = selectedCurrentRevision;
  const backupRevision = selectedGitRevision;
  let restored = false;
  await operation(async () => {
    const info = await tool("file_manager_git_restore", {
      path, commit: id, expected_revision: expectedRevision,
      expected_git_revision: backupRevision,
    });
    if (info.path !== path || typeof info.revision !== "string" ||
        info.restored_commit !== id) {
      throw new Error("Unexpected restore response");
    }
    closeHistory();
    tabs.delete(path);
    restored = true;
    status("Git revision restored. Refreshing the file…");
  });
  // The operation has released the busy lock; an earlier queueMicrotask here
  // ran while busy=true and silently prevented the refresh.
  if (restored && active?.path === path) {
    await openFile(path, true);
  }
}
function toggleDiff(): void {
  if (busy || !editing || !codeEditor) return;
  if (diffViewer) { closeDiff(); return; }
  el("diff-panel").hidden = false;
  diffViewer = new DiffView(el("diff-content"), active!.path, originalText, codeEditor.text);
}
function drawEditorControls(): void {
  el("edit").hidden = editing;
  el("diff").hidden = !editing;
  (el("diff") as HTMLButtonElement).disabled = !editing || busy || !editDirty;
  (el("history") as HTMLButtonElement).disabled = !connected || busy || !active || editing || !!logWindow || active.sizeBytes > EDIT_LIMIT;
  el("save").hidden = !editing;
  el("cancel-edit").hidden = !editing;
  (el("save") as HTMLButtonElement).disabled = !connected || busy || !editing || !editDirty;
  (el("cancel-edit") as HTMLButtonElement).disabled = !editing || busy;
  el("edit-mark").textContent = editing ? (editDirty ? "● Unsaved changes" : "Editing") : "";
}

let selectedHeading: string | null = null;

interface TabSnapshot {
  file: OpenedFile;
  text: string;
  cursor: Cursor | null;
  mode: ViewMode;
  heading: string | null;
  outline: OutlineHeading[];
}
const tabs = new Map<string, TabSnapshot>();
// At most two read-ahead requests; each key pins the file revision and line.
const pagePrefetch = new Map<string, Promise<JsonRecord | null>>();
function pageKey(path: string, revision: string, line: number): string {
  return JSON.stringify([path, revision, line]);
}
function prefetchNextPage(file: OpenedFile, cursor: Cursor | null): void {
  if (!cursor || cursor.kind !== "lines" ||
      file.sizeBytes > 64 * 1024 || file.sizeBytes < 4000) return;
  const key = pageKey(file.path, file.revision, cursor.line);
  window.setTimeout(() => {
    if (active?.path !== file.path || active.revision !== file.revision ||
        !tabs.has(file.path) || pagePrefetch.has(key)) return;
    if (pagePrefetch.size >= 2) {
      const oldest = pagePrefetch.keys().next().value;
      if (oldest) pagePrefetch.delete(oldest);
    }
    pagePrefetch.set(key, tool("file_viewer_read_text", {
      path: file.path, start_line: cursor.line, max_lines: 70,
      revision: file.revision,
    }).then((result) => result.revision === file.revision &&
      typeof result.content === "string" ? result : null).catch(() => null));
  }, 750);
}
let outlineCache: OutlineHeading[] = [];
let matches: Match[] = [];
let matchIndex = -1;
function snapshotCurrent(): void {
  // Log byte windows are not ordinary text revisions; preserve the prior text tab.
  if (!logWindow && active && tabs.has(active.path)) tabs.set(active.path, {
    file: active, text: currentText, cursor: continuation, mode: viewMode,
    heading: selectedHeading, outline: outlineCache,
  });
}
function renderTabs(): void {
  const container = el("tabs"); container.replaceChildren();
  for (const [path] of tabs) {
    const tab = document.createElement("button");
    tab.type = "button"; tab.className = "tab";
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", String(active?.path === path));
    const name = document.createElement("span");
    name.textContent = path.split("/").pop() || path;
    tab.title = path;
    tab.append(name);
    tab.addEventListener("click", () => { if (!busy) activateTab(path); });
    const close = document.createElement("span");
    close.className = "close-tab"; close.textContent = "×"; close.title = "Close tab";
    close.setAttribute("role", "button"); close.setAttribute("tabindex", "0");
    const closeIt = (event: Event) => { event.stopPropagation(); if (!busy) closeTab(path); };
    close.addEventListener("click", closeIt);
    close.addEventListener("keydown", (event: KeyboardEvent) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); closeIt(event); }
    });
    tab.append(close); container.append(tab);
  }
}
function performanceDetail(
  source: "cache" | "server", networkMs: number, serverMs: number | null,
  renderMs: number, totalMs: number,
): void {
  if (source === "cache") {
    el("perf-metrics").textContent =
      "Cached · MCP call 0 ms · UI render " +
      renderMs.toFixed(1) + " ms · Total " + totalMs.toFixed(1) +
      " ms (use Reload to check for changes)";
    return;
  }
  const server = serverMs !== null && Number.isFinite(serverMs) && serverMs >= 0
    ? serverMs : null;
  el("perf-metrics").textContent =
    "MCP call " + Math.round(networkMs) + " ms" +
    (server === null ? "" : " (server " + server.toFixed(1) +
    " ms / other " + Math.max(0, networkMs - server).toFixed(0) + " ms）") +
    " · UI processing " + renderMs.toFixed(1) +
    " ms · Total " + Math.round(totalMs) + " ms";
}
function activateTab(path: string): void {
  if (busy) return;
  const startedAt = performance.now();
  if (active?.path === path && !logWindow) {
    input().value = path;
    performanceDetail("cache", 0, null, 0, performance.now() - startedAt);
    status("Showing cached file · use Reload to check for changes");
    return;
  }
  if (!confirmDiscard()) return;
  closeHistory();
  resetEditor();
  snapshotCurrent();
  const tab = tabs.get(path);
  if (!tab) return;
  logWindow = null;
  active = tab.file; currentText = tab.text; continuation = tab.cursor;
  viewMode = tab.mode; selectedHeading = tab.heading;
  outlineCache = tab.outline;
  input().value = active.path;
  el("filename").textContent = active.path.split("/").pop() || active.path;
  el("fullpath").textContent = active.path;
  el("meta").textContent = String(active.totalLines) + " lines · " +
    active.sizeBytes.toLocaleString() + " B · Read only · Cached";
  renderOutline(outlineCache); updateMatches(); drawContent();
  renderTabs(); markSelectedFile(); controls();
  const elapsed = performance.now() - startedAt;
  performanceDetail("cache", 0, null, elapsed, elapsed);
  status("Opened cached file · use Reload to check for changes");
}
function closeTab(path: string): void {
  if (busy) return;
  if (active?.path === path && !confirmDiscard()) return;
  if (active?.path === path) closeHistory();
  if (active?.path === path) resetEditor();
  const current = active?.path === path;
  tabs.delete(path);
  if (current) {
    active = null; logWindow = null; continuation = null; currentText = ""; outlineCache = [];
    selectedHeading = null;
    const fallback = [...tabs.keys()].at(-1);
    if (fallback) activateTab(fallback);
    else {
      el("filename").textContent = "No file selected";
      el("fullpath").textContent = ""; el("meta").textContent = "Select a file";
      el("outline").replaceChildren(); el("source-code").textContent = "";
      el("preview-pane").replaceChildren();
      el("preview-pane").hidden = true; el("source-pane").hidden = false;
      updateMatches();
    }
  }
  renderTabs();controls();
}
function updateMatches(): void {
  matches = findMatches(currentText, (el("find-query") as HTMLInputElement).value);
  matchIndex = matches.length ? 0 : -1;
  updateFindControls();
}
function updateFindControls(): void {
  el("find-count").textContent = matches.length
    ? String(matchIndex + 1) + "/" + String(matches.length) + (matches.length === 200 ? "+" : "")
    : "0 results";
  (el("find-prev") as HTMLButtonElement).disabled = !matches.length;
  (el("find-next") as HTMLButtonElement).disabled = !matches.length;
}
function selectMatch(direction: number): void {
  if (!matches.length) return;
  matchIndex = (matchIndex + direction + matches.length) % matches.length;
  if (viewMode === "preview") switchView("source");
  else drawContent();
  updateFindControls();
}
function showFindHighlights(): void {
  if (!active || !matches.length || viewMode !== "source" || currentText.length > 80000) return;
  const node = el("source-code");
  // Plain text + mark elements only; no untrusted HTML is ever interpolated.
  const fragment = document.createDocumentFragment();
  let position = 0;
  for (let i = 0; i < matches.length; i++) {
    const hit = matches[i];
    fragment.append(document.createTextNode(currentText.slice(position, hit.start)));
    const mark = document.createElement("mark"); mark.className = "find-hit";
    if (i === matchIndex) { mark.classList.add("current"); mark.id = "current-find-hit"; }
    mark.textContent = currentText.slice(hit.start, hit.end);
    fragment.append(mark); position = hit.end;
  }
  fragment.append(document.createTextNode(currentText.slice(position)));
  node.replaceChildren(fragment);
  node.querySelector(".current")?.scrollIntoView({ block: "center", behavior: "auto" });
}


function status(message: string, error = false): void {
  const target = el("status");
  target.textContent = message;
  target.classList.toggle("error", error);
}

function controls(): void {
  const enabled = connected && !busy;
  (el("bench") as HTMLButtonElement).disabled = !enabled;
  (el("open") as HTMLButtonElement).disabled = !enabled;
  (el("folder") as HTMLButtonElement).disabled = !enabled;
  (el("refresh") as HTMLButtonElement).disabled = !enabled || !active;
  (el("tail") as HTMLButtonElement).disabled = !enabled;
  (el("diagnose") as HTMLButtonElement).disabled = !enabled;
  (el("log-before") as HTMLButtonElement).disabled = !enabled || !logWindow?.has_earlier;
  (el("log-after") as HTMLButtonElement).disabled = !enabled || !logWindow?.has_later;
  (el("log-check") as HTMLButtonElement).disabled = !enabled || !logWindow;

  (el("filename-search") as HTMLButtonElement).disabled = !enabled || !currentDirectory;
  (el("up") as HTMLButtonElement).disabled = !enabled || !currentDirectory;
  (el("more") as HTMLButtonElement).disabled = !enabled || !continuation;
  el("more").hidden = !continuation;
  (el("preview-tab") as HTMLButtonElement).disabled = !enabled || active?.kind !== "markdown";
  (el("source-tab") as HTMLButtonElement).disabled = !enabled || !active;
  (el("edit") as HTMLButtonElement).disabled = !enabled || !active ||
    !!logWindow || active.sizeBytes > EDIT_LIMIT;
  drawEditorControls();
  (el("keymap-mode") as HTMLSelectElement).disabled = busy;
  el("connection").textContent = connected ? "● Connected" : "○ Disconnected";
}

interface TimedResult {
  data: JsonRecord;
  hostMs: number;
  decodeMs: number;
}
async function timedTool(name: string, args: JsonRecord): Promise<TimedResult> {
  const started = performance.now();
  const response = await app.callServerTool({ name, arguments: args });
  const hostMs = performance.now() - started;
  const decodeStarted = performance.now();
  const data = decodeToolResult(response);
  return { data, hostMs, decodeMs: performance.now() - decodeStarted };
}
async function tool(name: string, args: JsonRecord): Promise<JsonRecord> {
  return (await timedTool(name, args)).data;
}

async function operation(action: () => Promise<void>): Promise<void> {
  if (!connected) {
    status("Waiting for MCP Apps host", true);
    return;
  }
  if (busy) return;
  busy = true;
  controls();
  try {
    await action();
  } catch (error) {
    status("Error: " + (error instanceof Error ? error.message : String(error)), true);
  } finally {
    busy = false;
    controls();
    if (queuedHostPath && connected) {
      const path = queuedHostPath;
      queuedHostPath = null;
      queueMicrotask(() => void openFile(path));
    }
  }
}

function navButton(container: HTMLElement, label: string, run: () => void): HTMLButtonElement {
  const button = document.createElement("button");
  button.className = "nav-item";
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", run);
  container.append(button);
  return button;
}

function renderTreeItems(parent: HTMLElement, directory: string, entries: FileEntry[], depth: number): void {
  parent.replaceChildren();
  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "subtle";
    empty.textContent = "No items";
    parent.append(empty);
  }
  for (const entry of entries) {
    if (!entry || typeof entry.name !== "string" || typeof entry.type !== "string") continue;
    let target: string;
    try { target = childPath(directory, entry.name); }
    catch { continue; }
    const isDir = entry.type === "directory";
    const row = document.createElement("div");
    row.className = "tree-row";
    parent.append(row);

    if (isDir) {
      const twisty = document.createElement("button");
      twisty.type = "button";
      twisty.className = "twisty";
      twisty.textContent = "▸";
      twisty.setAttribute("aria-label", entry.name + " expand");
      twisty.setAttribute("aria-expanded", "false");
      row.append(twisty);

      const label = navButton(row, "📁 " + entry.name, () => void toggle());
      const children = document.createElement("div");
      children.className = "tree-children";
      children.hidden = true;
      parent.append(children);
      let loaded = false;
      async function toggle(): Promise<void> {
        if (busy) return;
        if (!children.hidden) {
          children.hidden = true;
          twisty.textContent = "▸";
          twisty.setAttribute("aria-expanded", "false");
          return;
        }
        if (!loaded) {
          await operation(async () => {
            status("Loading folder…");
            const data = await tool("file_viewer_list", { path: target, limit: 70 });
            if (typeof data.path !== "string" || !Array.isArray(data.entries)) {
              throw new Error("Invalid directory listing");
            }
            renderTreeItems(children, data.path, data.entries as FileEntry[], depth + 1);
            loaded = true;
            if (data.truncated) {
              const hint = document.createElement("div");
              hint.className = "subtle";
              hint.textContent = "Showing up to 70 entries";
              children.append(hint);
            }
            status("Folder expanded");
          });
          if (!loaded) return;
        }
        children.hidden = false;
        twisty.textContent = "▾";
        twisty.setAttribute("aria-expanded", "true");
        label.focus({ preventScroll: true });
      }
      twisty.addEventListener("click", () => void toggle());
    } else {
      const pad = document.createElement("span");
      pad.style.width = "24px";
      pad.style.flexShrink = "0";
      row.append(pad);
      const button = navButton(row, "📄 " + entry.name, () => void openFile(target));
      button.dataset.filePath = target;
    }
  }
  markSelectedFile();
}

function markSelectedFile(): void {
  for (const item of el("entries").querySelectorAll<HTMLButtonElement>(".nav-item[data-file-path]")) {
    item.classList.toggle("nav-selected", item.dataset.filePath === active?.path);
  }
}

function rootTree(data: JsonRecord): void {
  if (typeof data.path !== "string" || !Array.isArray(data.entries)) {
    throw new Error("Invalid directory listing");
  }
  currentDirectory = data.path;
  el("directory-name").textContent = data.path;
  renderTreeItems(el("entries"), data.path, data.entries as FileEntry[], 0);
  el("directory-hint").textContent = data.truncated
    ? "Showing first 70 · Read only"
    : String(data.entries.length) + " entries · Read only";
}

async function openDirectory(path: string): Promise<void> {
  if (editing && !confirmDiscard()) return;
  await operation(async () => {
    status("Loading folder…");
    rootTree(await tool("file_viewer_list", { path, limit: 70 }));
    status("Folder opened");
  });
}

async function searchFileNames(): Promise<void> {
  if (!currentDirectory) return;
  const query = (el("filename-query") as HTMLInputElement).value.trim();
  if (!query) { status("Enter a filename query"); return; }
  await operation(async () => {
    const result = await tool("file_manager_search_names", {
      path: currentDirectory, query, limit: 40,
    });
    if (typeof result.path !== "string" || !Array.isArray(result.entries)) {
      throw new Error("Invalid search results");
    }
    renderTreeItems(el("entries"), result.path, result.entries as FileEntry[], 0);
    el("filename-search-note").textContent = result.truncated
      ? "Partial results (40 matches / 2,000 scanned)"
      : String(result.entries.length) + " filename matches";
    status("Filename search complete");
  });
}

function applyLogWindow(data: JsonRecord): void {
  if (editing) resetEditor();
  closeHistory();
  if (typeof data.path !== "string" || typeof data.content !== "string" ||
      typeof data.identity !== "string" || typeof data.revision !== "string") {
    throw new Error("Invalid log data");
  }
  logWindow = data as LogWindow;
  active = {
    path: logWindow.path, revision: logWindow.revision, kind: "text",
    sizeBytes: logWindow.size_bytes, totalLines: 0,
  };
  currentText = logWindow.content;
  continuation = null;
  selectedHeading = null;
  outlineCache = [];
  viewMode = "source";
  input().value = logWindow.path;
  el("filename").textContent = logWindow.path.split("/").pop() || logWindow.path;
  el("fullpath").textContent = logWindow.path;
  el("meta").textContent = String(logWindow.size_bytes) +
    " B · bytes " + String(logWindow.start_byte) + "–" +
    String(logWindow.end_byte) + " · Read only";
  renderOutline([]);
  updateMatches();
  drawContent();
  markSelectedFile();
}
async function moveLog(direction: "before" | "after"): Promise<void> {
  if (!logWindow) return;
  await operation(async () => {
    const previous = logWindow!;
    const offset = direction === "before" ? previous.start_byte : previous.end_byte;
    const data = await tool("file_manager_log_window", {
      path: previous.path, direction, offset, max_bytes: 4096,
    });
    if (data.identity !== previous.identity || data.revision !== previous.revision) {
      throw new Error("Log changed; reopen the tail");
    }
    applyLogWindow(data);
    status("Moved log " + (direction === "before" ? "previous" : "next") + " window");
  });
}
async function checkLog(): Promise<void> {
  if (!logWindow) return;
  await operation(async () => {
    const previous = logWindow!;
    const next = await tool("file_manager_log_status", { path: previous.path });
    if (next.identity !== previous.identity) {
      status("Log file replaced; reopen tail", true);
    } else if (Number(next.size_bytes) < previous.size_bytes) {
      status("Log truncated; reopen tail", true);
    } else if (Number(next.size_bytes) > previous.size_bytes) {
      status("Log appended; reopen tail for latest entries");
    } else if (next.revision !== previous.revision) {
      status("Log modified; reopen tail", true);
    } else {
      status("No log changes");
    }
  });
}
async function diagnoseLog(): Promise<void> {
  const path = typedPath() || active?.path;
  if (!path) { status("Select a log path", true); return; }
  await operation(async () => {
    const result = await tool("file_manager_diagnose", { path });
    const counts = result.counts_in_excerpt as Record<string, number> | undefined;
    if (!counts || !Array.isArray(result.evidence)) throw new Error("Invalid diagnostics result");
    const state = result.scf_status === "converged" ? "Convergence marker found"
      : result.scf_status === "not_converged" ? "Non-convergence marker found" : "Convergence unknown";
    const summary = [
      "Simple log-suffix diagnostics (not whole-file analysis)",
      "SCF: " + state,
      "Errors " + String(counts.error ?? 0) + " · Warnings " +
        String(counts.warning ?? 0) + " · Timings " + String(counts.timing ?? 0),
      "Range: " + String(result.start_byte) + "–" + String(result.end_byte) + " bytes",
      ...result.evidence.slice(-8).map((e: {kind:string;text:string}) => "[" + e.kind + "] " + e.text),
    ].join("\n");
    const panel = el("diagnosis");panel.hidden = false; panel.textContent = summary;
    status("Log diagnostics complete");
  });
}
async function openLogTail(): Promise<void> {
  if (editing && !confirmDiscard()) return;
  if (editing) resetEditor();
  closeHistory();
  const path = typedPath() || active?.path;
  if (!path) { status("Enter an absolute log path", true); return; }
  await operation(async () => {
    const data = await tool("file_manager_log_window", {
      path, direction: "tail", max_bytes: 4096,
    });
    applyLogWindow(data);
    status("Showing log tail (no auto-refresh)");
  });
}

function renderOutline(headings: OutlineHeading[]): void {
  const outline = el("outline");
  outline.replaceChildren();
  if (!headings.length) {
    const empty = document.createElement("span");
    empty.className = "subtle";
    empty.textContent = "No headings";
    outline.append(empty);
  }
  for (const heading of headings) {
    if (!heading || typeof heading.id !== "string" || typeof heading.title !== "string") continue;
    const btn = navButton(outline, heading.title, () => void openSection(heading.id));
    btn.style.paddingLeft = String(10 + Math.min(Math.max(heading.level - 1, 0), 5) * 12) + "px";
    btn.dataset.headingId = heading.id;
  }
  markHeading();
}

function markHeading(): void {
  for (const btn of el("outline").querySelectorAll<HTMLButtonElement>("[data-heading-id]")) {
    btn.classList.toggle("nav-selected", btn.dataset.headingId === selectedHeading);
  }
}

function drawContent(): void {
  const source = el("source-pane");
  const preview = el("preview-pane");
  const inPreview = viewMode === "preview" && active?.kind === "markdown";
  source.hidden = editing || inPreview;
  preview.hidden = editing || !inPreview;
  el("editor-pane").hidden = !editing;
  (el("source-tab") as HTMLButtonElement).setAttribute("aria-pressed", String(!inPreview));
  (el("preview-tab") as HTMLButtonElement).setAttribute("aria-pressed", String(inPreview));
  el("view-note").textContent = inPreview
    ? "Markdown preview · images hidden"
    : (active && languageFor(active.path) ? "Syntax highlighting" : "UTF-8 text");

  if (inPreview) {
    renderMarkdown(preview, currentText);
  } else {
    renderSource(el("source-code"), active?.path ?? "", currentText);
    showFindHighlights();
  }
}

function switchView(mode: ViewMode): void {
  if (editing) return;
  if (!active || (mode === "preview" && active.kind !== "markdown")) return;
  viewMode = mode;
  snapshotCurrent();drawContent();
}

async function openFile(path: string, forceReload = false): Promise<void> {
  if (busy) return;
  const requestedPath = path.trim();
  if (!requestedPath) { status("Enter a file path", true); return; }
  if (editing && !confirmDiscard()) return;
  closeHistory();
  if (editing) resetEditor();
  // A file-tree click reuses the in-memory snapshot; only explicit reload
  // requests a fresh revision from the remote cluster.
  if (!forceReload && !busy && tabs.has(requestedPath)) {
    activateTab(requestedPath);
    setExplorerOpen(false);
    return;
  }
  await operation(async () => {
    status("Opening file…");
    const openedAt = performance.now();
    const timed = await timedTool("file_manager_open_fast", { path: requestedPath });
    const info = timed.data;
    const responseAt = performance.now();
    if (typeof info.path !== "string" || typeof info.revision !== "string" ||
        typeof info.content !== "string") {
      throw new Error("Invalid file metadata");
    }
    const opened: OpenedFile = {
      path: info.path, revision: info.revision,
      totalLines: Number(info.total_lines) || 0,
      sizeBytes: Number(info.size_bytes) || 0,
      kind: info.kind === "markdown" ? "markdown" : "text",
    };
    const headings = Array.isArray(info.headings) ? info.headings as OutlineHeading[] : [];
    const first = info;
    // Keep at most five bounded snapshots; no persistence to the local disk.
    if (forceReload) pagePrefetch.clear();
    snapshotCurrent();
    if (!tabs.has(opened.path) && tabs.size >= MAX_TABS) {
      const oldest = tabs.keys().next().value;
      if (oldest) tabs.delete(oldest);
    }
    logWindow = null;
    active = opened;
    continuation = nextCursor({ kind: "lines", line: 1 }, first);
    selectedHeading = null;
    outlineCache = headings;
    currentText = first.content as string;
    input().value = opened.path;
    el("filename").textContent = opened.path.split("/").pop() || opened.path;
    el("fullpath").textContent = opened.path;
    el("meta").textContent =
      String(opened.totalLines) + " lines · " + opened.sizeBytes.toLocaleString() + " B · Read only";
    viewMode = opened.kind === "markdown" ? "preview" : "source";
    renderOutline(headings);
    tabs.set(opened.path, { file: opened, text: currentText, cursor: continuation, mode: viewMode, heading: selectedHeading, outline: headings });
    updateMatches();
    renderTabs();
    drawContent();
    markSelectedFile();
    setExplorerOpen(false);
    const finishedAt = performance.now();
    const networkMs = responseAt - openedAt;
    const renderMs = finishedAt - responseAt;
    const serverMs = typeof info.server_elapsed_ms === "number" ? info.server_elapsed_ms : null;
    performanceDetail("server", networkMs, serverMs, renderMs, finishedAt - openedAt);
    el("perf-metrics").textContent += " · Host call " + timed.hostMs.toFixed(1) +
      " ms / decode " + timed.decodeMs.toFixed(1) + " ms";
    status("Opened file · " + Math.round(finishedAt - openedAt) + " ms (details below)");
    prefetchNextPage(opened, continuation);
    // Sidebar refresh is best-effort; the initial file response is complete.
    const parent = parentDirectory(opened.path);
    if (!el("explorer-panel").hidden && parent !== currentDirectory) {
      void tool("file_viewer_list", { path: parent, limit: 70 }).then((data) => {
        if (active?.path === opened.path) rootTree(data);
      }).catch(() => {
        if (active?.path === opened.path)
          el("directory-hint").textContent = "Could not load directory list";
      });
    }
  });
}

async function openSection(id: string): Promise<void> {
  if (editing) { status("Finish editing before navigating sections.", true); return; }
  if (!active) return;
  await operation(async () => {
    const file = active!;
    status("Loading section…");
    const data = await tool("file_viewer_read_section", {
      path: file.path, section_id: id, revision: file.revision, offset: 0, max_chars: 3000,
    });
    if (typeof data.content !== "string") throw new Error("Invalid section content");
    continuation = nextCursor({ kind: "section", id, offset: 0 }, data);
    selectedHeading = id;
    currentText = data.content;
    snapshotCurrent();updateMatches();
    markHeading();
    drawContent();
    status("Section: " + String(data.start_line) + "–" + String(data.end_line) + " lines");
  });
}

async function readMore(): Promise<void> {
  if (editing) { status("Finish editing before loading more.", true); return; }
  if (!active || !continuation) return;
  await operation(async () => {
    if (currentText.length >= MAX_DOCUMENT_CHARS) {
      continuation = null;
      status("Display limit reached (180,000 characters); reopen the file.", true);
      return;
    }
    const c = continuation!;
    const file = active!;
    status("Loading more…");
    let result: JsonRecord;
    if (c.kind === "lines") {
      const key = pageKey(file.path, file.revision, c.line);
      const pending = pagePrefetch.get(key);
      if (pending) pagePrefetch.delete(key);
      result = (pending ? await pending : null) ?? await tool("file_viewer_read_text", {
        path: file.path, start_line: c.line, max_lines: 70, revision: file.revision,
      });
    } else {
      result = await tool("file_viewer_read_section", {
        path: file.path, section_id: c.id, revision: file.revision,
        offset: c.offset, max_chars: 3000,
      });
    }
    if (typeof result.content !== "string") throw new Error("Invalid file content");
    const next = nextCursor(c, result);
    if (currentText.length + result.content.length > MAX_DOCUMENT_CHARS) {
      continuation = null;
      status("Display limit reached; open another range.", true);
      return;
    }
    currentText += result.content;
    continuation = next;
    snapshotCurrent();updateMatches();
    drawContent();
    status(continuation ? "More content available" : "End of file");
  });
}

async function startEditing(): Promise<void> {
  if (!active || editing || logWindow || active.sizeBytes > EDIT_LIMIT) return;
  await operation(async () => {
    const file = active!;
    status("Loading complete file for editing…");
    const complete = await readCurrentFull(file);
    closeHistory();
    originalText = complete.text;
    editRevision = complete.revision;
    editDirty = false;
    editing = true;
    drawContent();
    codeEditor = new CodeEditor(
      el("editor-pane"), file.path, originalText, keymapMode,
      text => {
        editDirty = text !== originalText;
        closeDiff();
        drawEditorControls();
      },
    );
    controls();
    codeEditor.focus();
    status("Editing local buffer. Save to write changes to the cluster.");
  });
}
async function saveEdits(): Promise<void> {
  if (busy || !editing || !active || !editDirty) return;
  const updated = codeEditor?.text;
  if (updated === undefined) { status("Editor is not initialized.", true); return; }
  if (new TextEncoder().encode(updated).length > EDIT_LIMIT) {
    status("Edited content exceeds the 64 KiB limit.", true);
    return;
  }
  await operation(async () => {
    const file = active!;
    status("Checking revision and saving…");
    const savingEditor = codeEditor;
    savingEditor?.setReadOnly(true);
    let result: JsonRecord;
    try {
      result = await tool("file_manager_edit_save", {
        path: file.path, expected_revision: editRevision, content: updated,
      });
    } finally {
      if (savingEditor === codeEditor) savingEditor?.setReadOnly(false);
    }
    if (typeof result.revision !== "string" || result.path !== file.path) {
      throw new Error("Invalid save acknowledgement.");
    }
    resetEditor();
    tabs.delete(file.path);
    active = { ...file, revision: result.revision,
      sizeBytes: Number(result.size_bytes) || 0,
      totalLines: updated.length === 0 ? 0 : updated.split("\n").length };
    currentText = updated;
    continuation = null;
    selectedHeading = null;
    viewMode = "source";
    outlineCache = [];
    tabs.set(active.path, { file: active, text: currentText,
      cursor: null, mode: viewMode, heading: null, outline: [] });
    el("meta").textContent = active.totalLines + " lines · " +
      active.sizeBytes.toLocaleString() + " B · Saved";
    renderOutline([]); renderTabs(); updateMatches(); drawContent(); controls();
    status("Saved successfully.");
  });
}
function cancelEditing(): void {
  if (busy || !editing || !confirmDiscard()) return;
  resetEditor();
  drawContent(); controls(); status("Editing canceled.");
}
(el("keymap-mode") as HTMLSelectElement).addEventListener("change", () => {
  const selector = el("keymap-mode") as HTMLSelectElement;
  if (busy) { selector.value = keymapMode; return; }
  const selected = selector.value;
  keymapMode = selected === "vim" ? "vim" : "standard";
  codeEditor?.setKeymap(keymapMode);
  status(keymapMode === "vim"
    ? (editing
        ? "Vim enabled. Press i to enter INSERT; Esc returns to NORMAL."
        : "Vim selected. Click Edit, then press i for INSERT.")
    : "Standard keybindings enabled.");
});
Vim.defineEx("write", "w", () => {
  if (editDirty) void saveEdits();
  else status("No changes to save.");
});
Vim.defineEx("quit", "q", () => cancelEditing());
Vim.defineEx("wq", "wq", () => {
  if (editDirty) void saveEdits();
  else cancelEditing();
});
el("diff").addEventListener("click", toggleDiff);
el("history").addEventListener("click", () => void openHistory());
el("edit").addEventListener("click", () => void startEditing());
el("save").addEventListener("click", () => void saveEdits());
el("cancel-edit").addEventListener("click", cancelEditing);
document.addEventListener("keydown", (event: KeyboardEvent) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s" && editing) {
    event.preventDefault(); void saveEdits();
  }
});
window.addEventListener("beforeunload", (event) => {
  if (editing && editDirty) event.preventDefault();
});

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const i = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[i] : (sorted[i - 1] + sorted[i]) / 2;
}
async function benchmarkConnection(): Promise<void> {
  const path = typedPath() || active?.path;
  if (!connected || busy || !path) {
    status("Select a connected file to benchmark", true);
    return;
  }
  busy = true; controls();
  const lines: string[] = ["MCP Apps latency (3 calls per tool)"];
  try {
    const records: Record<string, number[]> = { info: [], fast: [] };
    for (let i = 0; i < 6; i++) {
      const kind = i % 2 === 0 ? "info" : "fast";
      const name = kind === "info" ? "file_viewer_info" : "file_manager_open_fast";
      status("Benchmarking MCP calls: " + (i + 1) + "/6");
      const result = await timedTool(name, { path });
      const server = result.data.server_elapsed_ms;
      const note = typeof server === "number" && Number.isFinite(server)
        ? ", server " + server.toFixed(1) + " ms" : "";
      records[kind].push(result.hostMs);
      lines.push(name + ": host " + result.hostMs.toFixed(1) +
        " ms, decode " + result.decodeMs.toFixed(2) + " ms" + note);
    }
    lines.push("Median (3 calls each): metadata " + median(records.info).toFixed(1) +
      " ms / fast-open " + median(records.fast).toFixed(1) + " ms");
    lines.push("Host latency includes transport/relay/queue time; breakdown unavailable.");
    status("Benchmark complete");
  } catch (error) {
    lines.push("Benchmark failed: " + String(error));
    status("Benchmark failed", true);
  } finally {
    el("bench-report").textContent = lines.join("\n");
    busy = false; controls();
  }
}
function typedPath(): string { return input().value.trim(); }
el("bench").addEventListener("click", () => void benchmarkConnection());
el("explorer-toggle").addEventListener("click", toggleExplorer);
el("open").addEventListener("click", () => void openFile(typedPath()));
input().addEventListener("keydown", (event: KeyboardEvent) => {
  if (event.key === "Enter") { event.preventDefault(); void openFile(typedPath()); }
});
el("refresh").addEventListener("click", () => { if (active) void openFile(active.path, true); });
el("folder").addEventListener("click", () => {
  const path = typedPath() || active?.path;
  if (!path) { status("Enter a file path", true); return; }
  try { setExplorerOpen(true); void openDirectory(parentDirectory(path)); }
  catch (error) { status(String(error), true); }
});
el("up").addEventListener("click", () => {
  if (!currentDirectory) return;
  try { void openDirectory(parentDirectory(currentDirectory)); }
  catch (error) { status(String(error), true); }
});
el("more").addEventListener("click", () => void readMore());
el("tail").addEventListener("click", () => void openLogTail());
el("diagnose").addEventListener("click", () => void diagnoseLog());
el("log-before").addEventListener("click", () => void moveLog("before"));
el("log-after").addEventListener("click", () => void moveLog("after"));
el("log-check").addEventListener("click", () => void checkLog());
el("filename-search").addEventListener("click", () => void searchFileNames());
el("filename-query").addEventListener("keydown", (event: KeyboardEvent) => {
  if (event.key === "Enter") { event.preventDefault(); void searchFileNames(); }
});
el("find-query").addEventListener("input", () => { updateMatches(); drawContent(); });
el("find-query").addEventListener("keydown", (event: KeyboardEvent) => {
  if (event.key === "Enter") { event.preventDefault(); selectMatch(event.shiftKey ? -1 : 1); }
});
el("find-prev").addEventListener("click", () => selectMatch(-1));
el("find-next").addEventListener("click", () => selectMatch(1));
el("source-tab").addEventListener("click", () => switchView("source"));
el("preview-tab").addEventListener("click", () => switchView("preview"));

app.ontoolinput = (params) => {
  const path = params.arguments?.path;
  if (typeof path !== "string" || !path.trim()) return;
  queuedHostPath = path;
  input().value = path;
  if (connected && !busy) {
    queuedHostPath = null;
    void openFile(path);
  }
};
app.connect().then(() => {
  connected = true;
  status("Connected to MCP Apps host");
  controls();
  if (queuedHostPath) {
    const path = queuedHostPath;
    queuedHostPath = null;
    void openFile(path);
  }
}).catch((error) => {
  status("Connection failed: " + String(error), true);
  controls();
});
controls();
