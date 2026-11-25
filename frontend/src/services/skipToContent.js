export function focusMainContent(event) {
  const document = event?.currentTarget?.ownerDocument;
  document?.getElementById("main-content")?.focus();
}
