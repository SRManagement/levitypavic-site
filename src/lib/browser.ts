// Detects if the site is being viewed inside a social app's in-app browser
// (Instagram, TikTok, Facebook, etc). These are webviews, not the real
// browser, and can cause problems with payment/subscription flows on
// destination sites like Fanvue — so we route those clicks out to the
// user's actual default browser instead of just opening a new tab.

export function isInAppBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  return /Instagram|FBAN|FBAV|TikTok|Snapchat|Line\//i.test(ua);
}

function isAndroid(): boolean {
  return typeof navigator !== "undefined" && /Android/i.test(navigator.userAgent);
}

function isIOS(): boolean {
  return (
    typeof navigator !== "undefined" &&
    /iPhone|iPad|iPod/i.test(navigator.userAgent)
  );
}

// Opens a URL, breaking out of an in-app webview into the real browser
// where possible.
export function openExternal(url: string) {
  if (!isInAppBrowser()) {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }

  if (isAndroid()) {
    // Android intent URLs force the link open in Chrome (or the user's
    // default browser) instead of the in-app webview.
    const stripped = url.replace(/^https?:\/\//, "");
    const intentUrl = `intent://${stripped}#Intent;scheme=https;package=com.android.chrome;end`;
    window.location.href = intentUrl;
    // Fallback in case the intent scheme fails to resolve
    setTimeout(() => {
      window.location.href = url;
    }, 1200);
    return;
  }

  if (isIOS()) {
    // iOS in-app webviews don't expose a reliable JS-only way to force
    // Safari. We navigate directly, which works for most modern flows;
    // callers should still show a "tap ••• → open in browser" hint as a
    // fallback since it's not 100% guaranteed on every app version.
    window.location.href = url;
    return;
  }

  window.open(url, "_blank", "noopener,noreferrer");
}
