import { Compartment, EditorState, type Extension } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { indentUnit, StreamLanguage } from "@codemirror/language";
import { indentWithTab } from "@codemirror/commands";
import { basicSetup } from "codemirror";
import { python } from "@codemirror/lang-python";
import { cpp } from "@codemirror/lang-cpp";
import { javascript } from "@codemirror/lang-javascript";
import { markdown } from "@codemirror/lang-markdown";
import { json } from "@codemirror/lang-json";
import { fortran } from "@codemirror/legacy-modes/mode/fortran";
import { shell } from "@codemirror/legacy-modes/mode/shell";
import { vim } from "@replit/codemirror-vim";

export type KeymapMode = "standard" | "vim";

export function editorLanguage(path: string): Extension {
  const filename = path.split("/").pop()?.toLowerCase() || "";
  if (/\.(f|for|f77|f90|f95|f03|f08)$/.test(filename)) {
    return StreamLanguage.define(fortran);
  }
  if (/\.(c|cc|cpp|cxx|h|hh|hpp|hxx)$/.test(filename)) return cpp();
  if (/\.py$/.test(filename)) return python();
  if (/\.(js|jsx|ts|tsx)$/.test(filename)) {
    return javascript({ typescript: /\.(ts|tsx)$/.test(filename), jsx: /\.(jsx|tsx)$/.test(filename) });
  }
  if (/\.(md|markdown)$/.test(filename)) return markdown();
  if (/\.(json|jsonc)$/.test(filename)) return json();
  if (/\.(sh|bash|zsh|fish)$/.test(filename) || filename === "bashrc" ||
      filename === ".bashrc" || filename === ".profile") {
    return StreamLanguage.define(shell);
  }
  return [];
}

export class CodeEditor {
  private readonly view: EditorView;
  private readonly keymapCompartment = new Compartment();
  private readonly editableCompartment = new Compartment();

  constructor(
    parent: HTMLElement,
    path: string,
    content: string,
    mode: KeymapMode,
    onChange: (text: string) => void,
  ) {
    this.view = new EditorView({
      doc: content,
      parent,
      extensions: [
        this.keymapCompartment.of(mode === "vim" ? vim({ status: true }) : []),
        this.editableCompartment.of([
          EditorView.editable.of(true),
          EditorState.readOnly.of(false),
        ]),
        basicSetup,
        EditorState.tabSize.of(4),
        indentUnit.of("    "),
        keymap.of([indentWithTab]),
        editorLanguage(path),
        EditorView.theme({
          "&": {
            height: "100%",
            fontSize: "12.5px",
            color: "var(--ink)",
            backgroundColor: "var(--bg)",
          },
          ".cm-scroller": {
            flex: "1",
            minHeight: "0",
            overflow: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
            lineHeight: "1.7",
          },
          ".cm-panels-bottom": {
            backgroundColor: "var(--surface)",
            color: "var(--ink)",
            borderTop: "1px solid var(--border)",
          },
          ".cm-vim-panel": {
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
            fontSize: "12px",
            minHeight: "25px",
            padding: "3px 10px",
          },
          ".cm-gutters": {
            backgroundColor: "var(--surface)",
            color: "var(--muted)",
            borderRight: "1px solid var(--border)",
          },
          ".cm-activeLine": { backgroundColor: "var(--selected)" },
          ".cm-activeLineGutter": { backgroundColor: "var(--selected)" },
        }),
        EditorView.updateListener.of(update => {
          if (update.docChanged) onChange(update.state.doc.toString());
        }),
      ],
    });
  }

  get text(): string {
    return this.view.state.doc.toString();
  }

  setKeymap(mode: KeymapMode): void {
    this.view.dispatch({
      effects: this.keymapCompartment.reconfigure(mode === "vim" ? vim({ status: true }) : []),
    });
    // A <select> takes keyboard focus; restore it to the editor after switching.
    this.view.focus();
  }

  setReadOnly(value: boolean): void {
    this.view.dispatch({
      effects: this.editableCompartment.reconfigure([
        EditorView.editable.of(!value),
        EditorState.readOnly.of(value),
      ]),
    });
  }

  focus(): void {
    this.view.focus();
  }

  destroy(): void {
    this.view.destroy();
  }
}
