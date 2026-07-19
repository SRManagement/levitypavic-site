"use client";

import { useEffect, useState } from "react";
import { isInAppBrowser } from "@/lib/browser";

export default function InAppBrowserBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Only ever runs in the browser, after mount — avoids any
    // server/client mismatch, and lets us safely read navigator.userAgent.
    if (isInAppBrowser() && !sessionStorage.getItem("dismissedBrowserBanner")) {
      setShow(true);
    }
  }, []);

  if (!show) return null;

  return (
    <div className="sticky top-0 z-[90] w-full bg-red px-4 py-3 text-center text-xs font-medium text-cream">
      <span>
        For the best experience (and so links work correctly), tap{" "}
        <strong>•••</strong> or <strong>⋮</strong> at the top of this screen,
        then choose <strong>&quot;Open in Browser&quot;</strong>.
      </span>
      <button
        onClick={() => {
          setShow(false);
          sessionStorage.setItem("dismissedBrowserBanner", "1");
        }}
        className="ml-3 underline underline-offset-2"
      >
        dismiss
      </button>
    </div>
  );
}
