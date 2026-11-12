/** Labels for the compact ChatGPT File Manager launcher. */

export interface LaunchDetails {
  filename: string;
  fileType: "PDF" | "画像" | "Markdown" | "テキスト" | "ファイルブラウザー";
}

/** Derive safe, readable labels without interpreting HTML in a path. */
export function launchDetails(path: unknown): LaunchDetails {
  if (typeof path !== "string" || !path.trim()) {
    return { filename: "HPC File Browser", fileType: "ファイルブラウザー" };
  }
  const normalized = path.trim().replace(/\/+$/, "");
  const filename = normalized.split("/").pop() || "HPC File Browser";
  const extension = filename.toLowerCase().split(".").pop() ?? "";
  const fileType = extension === "pdf" ? "PDF"
    : ["png", "jpg", "jpeg", "gif", "webp"].includes(extension) ? "画像"
    : ["md", "markdown"].includes(extension) ? "Markdown" : "テキスト";
  return { filename, fileType };
}

/** Show server host identity independently of Tabby/WinSCP default names. */
export function launchHost(value: unknown): string {
  return typeof value === "string" && /^[a-z0-9-]{1,64}$/i.test(value)
    ? value
    : "HPC";
}
