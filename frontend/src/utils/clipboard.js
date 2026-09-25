// The fallback also supports fleet consoles served over plain HTTP on a LAN.
export async function copyText(text) {
  if (globalThis.navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Permissions or browser policy may block the Clipboard API.
    }
  }

  const previousFocus = document.activeElement;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.readOnly = true;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  try {
    textarea.select();
    if (!document.execCommand("copy")) throw new Error("Clipboard access was denied.");
  } finally {
    textarea.remove();
    previousFocus?.focus({ preventScroll: true });
  }
}
