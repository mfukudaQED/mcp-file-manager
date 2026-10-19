/** Construct copy-only targets for local desktop applications. */

export function tabbyProfileUrl(rawProfile: string): string {
  const profile = rawProfile.trim();
  if (!profile || profile.length > 128 || /[\x00-\x1f\x7f]/.test(profile)) {
    throw new Error("Enter a valid Tabby profile name.");
  }
  return "tabby://profile?profileName=" + encodeURIComponent(profile);
}

export function copyableRemotePath(rawPath: string): string {
  const path = rawPath.trim();
  if (!path.startsWith("/") || /[\x00-\x1f\x7f]/.test(path)) {
    throw new Error("Select an absolute Linux path first.");
  }
  return path;
}

export function winScpDirectoryPath(
  path: string,
  isSelectedFile: boolean,
): string {
  const absolute = copyableRemotePath(path);
  if (!isSelectedFile) return absolute.endsWith("/") ? absolute : absolute + "/";
  const trimmed = absolute.replace(/\/+$/, "");
  const slash = trimmed.lastIndexOf("/");
  return slash > 0 ? trimmed.slice(0, slash) + "/" : "/";
}

export function winScpDirectoryUrl(rawSite: string, remoteDirectory: string): string {
  const site = rawSite.trim();
  // Restrict the authority to hostname-like stored site names, never credentials.
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(site)) {
    throw new Error("Enter a hostname-like WinSCP saved site (no user/password).");
  }
  const path = copyableRemotePath(remoteDirectory);
  const encoded = path.split("/").filter(Boolean).map(encodeURIComponent).join("/");
  // A trailing slash is critical: WinSCP otherwise may download a file.
  return "winscp-sftp://" + site + "/" + (encoded ? encoded + "/" : "");
}
