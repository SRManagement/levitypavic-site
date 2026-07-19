"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { isInAppBrowser } from "@/lib/browser";

export default function AgeGate({
  open,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [inApp, setInApp] = useState(false);

  useEffect(() => {
    setInApp(isInAppBrowser());
  }, []);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 px-4 pb-6 sm:items-center sm:pb-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onCancel}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="age-gate-title"
            className="w-full max-w-xs rounded-3xl border border-white/10 bg-surface p-6 text-center"
            initial={{ y: 30, opacity: 0, scale: 0.96 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 20, opacity: 0, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-pink">
              18+
            </p>
            <h2
              id="age-gate-title"
              className="mt-2 text-lg font-semibold text-cream"
            >
              adults-only content ahead
            </h2>

            {inApp ? (
              // Inside Instagram's in-app browser: skip the confirm/cancel
              // step entirely and go straight to the only real path out —
              // manually opening in the external browser.
              <div className="mt-4 rounded-2xl border border-white/10 bg-bg/60 p-4 text-left">
                <p className="text-center text-xs font-semibold uppercase tracking-wide text-pink">
                  to visit this link
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-white/10">
                    <DotsIcon />
                  </span>
                  <p className="text-xs text-cream/90">
                    Tap the <strong>&quot;•••&quot;</strong> icon in the top
                    right
                  </p>
                </div>
                <div className="mt-2.5 flex items-center gap-3">
                  <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-white/10">
                    <BrowserIcon />
                  </span>
                  <p className="text-xs text-cream/90">
                    Select{" "}
                    <strong>&quot;Open in External Browser&quot;</strong>
                  </p>
                </div>
              </div>
            ) : (
              // Already in a real browser — the standard age confirmation.
              <>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  you&apos;re about to leave this page for content intended
                  for viewers 18 and older. confirm your age to continue.
                </p>

                <button
                  onClick={onConfirm}
                  className="mt-5 w-full rounded-full py-3.5 text-sm font-semibold text-bg"
                  style={{ background: "var(--pink)" }}
                >
                  I&apos;m 18 or older — continue
                </button>
                <button
                  onClick={onCancel}
                  className="mt-2 w-full rounded-full py-3 text-sm text-muted"
                >
                  go back
                </button>
              </>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function DotsIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--pink)" strokeWidth="2.4" strokeLinecap="round">
      <circle cx="5" cy="12" r="1.4" fill="var(--pink)" stroke="none" />
      <circle cx="12" cy="12" r="1.4" fill="var(--pink)" stroke="none" />
      <circle cx="19" cy="12" r="1.4" fill="var(--pink)" stroke="none" />
    </svg>
  );
}

function BrowserIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--pink)" strokeWidth="1.8">
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="M3 8.5h18" strokeLinecap="round" />
      <path d="M13.5 12.5h4.5v4.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M18 12.5l-5.5 5.5" strokeLinecap="round" />
    </svg>
  );
}
