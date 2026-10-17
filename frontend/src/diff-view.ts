import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { basicSetup } from "codemirror";
import { unifiedMergeView } from "@codemirror/merge";
import { editorLanguage } from "./code-editor";

export class DiffView {
  private view: EditorView;

  constructor(parent: HTMLElement, path: string, original: string, changed: string) {
    parent.replaceChildren();
    this.view = new EditorView({
      parent,
      doc: changed,
      extensions: [
        basicSetup,
        EditorState.readOnly.of(true),
        EditorView.editable.of(false),
        editorLanguage(path),
        unifiedMergeView({
          original,
          mergeControls: false,
          highlightChanges: true,
          gutter: true,
        }),
        EditorView.theme({
          "&": { maxHeight: "275px", fontSize: "12px", background: "var(--bg)" },
          ".cm-scroller": { maxHeight: "275px", overflow: "auto" },
        }),
      ],
    });
  }

  destroy(): void {
    this.view.destroy();
  }
}
