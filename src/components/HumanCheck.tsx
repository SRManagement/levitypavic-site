"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

// Cloudflare Turnstile — the "checking you're real" step. Runs silently for
// almost everyone (no puzzle, no checkbox); Cloudflare only shows a single
// tap-to-confirm box if it's unsure about a visitor.

type Turnstile = {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  reset: (id?: string) => void;
  remove: (id?: string) => void;
};

declare global {
  interface Window {
    turnstile?: Turnstile;
  }
}

const SCRIPT_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

function loadTurnstile(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${SCRIPT_SRC}"]`
    );
    const script = existing ?? document.createElement("script");
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("turnstile load failed")));
    if (!existing) {
      script.src = SCRIPT_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
  });
}

// Error codes starting with 3 or 6 mean Cloudflare thinks it's a bot, and
// 1106xx is a timeout — those get a "try again" button. Anything else is a
// setup or loading problem (wrong key, domain not added, Cloudflare script
// blocked), and in those cases we let the visitor through rather than lock
// real fans out of the page.
function isChallengeFailure(code: unknown) {
  return /^(3|6|1106)/.test(String(code ?? ""));
}

export default function HumanCheck({
  siteKey,
  onPass,
}: {
  siteKey: string;
  onPass: () => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);
  const passed = useRef(false);
  const onPassRef = useRef(onPass);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    onPassRef.current = onPass;
  }, [onPass]);

  useEffect(() => {
    let cancelled = false;

    function pass() {
      if (passed.current || cancelled) return;
      passed.current = true;
      onPassRef.current();
    }

    async function verify(token: string) {
      try {
        const res = await fetch("/api/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        const data = (await res.json()) as { success?: boolean };
        if (data.success) pass();
        else if (!cancelled) setFailed(true);
      } catch {
        // Our own server didn't answer — don't block the visitor over it.
        pass();
      }
    }

    loadTurnstile()
      .then(() => {
        if (cancelled || !boxRef.current || !window.turnstile) return;
        widgetId.current = window.turnstile.render(boxRef.current, {
          sitekey: siteKey,
          theme: "dark",
          appearance: "interaction-only",
          callback: (token: string) => {
            setFailed(false);
            verify(token);
          },
          "error-callback": (code: string) => {
            if (isChallengeFailure(code)) setFailed(true);
            else pass();
            return true;
          },
        });
      })
      .catch(() => pass());

    return () => {
      cancelled = true;
      if (widgetId.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetId.current);
        } catch {
          // already gone
        }
      }
      widgetId.current = null;
    };
  }, [siteKey]);

  function retry() {
    setFailed(false);
    if (widgetId.current && window.turnstile) {
      window.turnstile.reset(widgetId.current);
    }
  }

  return (
    <div className="fixed inset-0 z-[105] flex flex-col items-center justify-center bg-black px-6 text-center">
      {/* Text only fades in if the check is taking a while — on a normal
          sub-second check the visitor just sees black, then the intro,
          exactly like before. */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.4 }}
        className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted"
      >
        {failed ? "couldn't verify" : "verifying"}
      </motion.p>

      <div ref={boxRef} className="mt-5" />

      {failed && (
        <button
          onClick={retry}
          className="font-mono mt-4 border border-white/20 px-5 py-2.5 text-[10px] uppercase tracking-[0.25em] text-cream active:opacity-60"
        >
          try again
        </button>
      )}
    </div>
  );
}
