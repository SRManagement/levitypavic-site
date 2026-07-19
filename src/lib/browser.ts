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
    // Instagram's iOS in-app browser doesn't implement its own handling
    // for target="_blank" links — when a real anchor click requests a
    // new tab, WebKit falls back to handing it off to Safari since
    // there's nowhere else for it to go. A programmatic click on a real
    // <a target="_blank"> element triggers that fallback; window.location
    // does not, since it just navigates within the same webview.
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    return;
  }

  window.open(url, "_blank", "noopener,noreferrer");
}
