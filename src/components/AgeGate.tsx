"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { isInAppBrowser } from "@/lib/browser";

export default function AgeGate({
  open,
  almostThere = false,
  fanvueUrl,
  onConfirm,
  onInAppAttempt,
  onCancel,
}: {
  open: boolean;
  almostThere?: boolean;
  fanvueUrl: string;
  onConfirm: () => void;
  onInAppAttempt: () => void;
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
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onCancel}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="age-gate-title"
            className="w-full max-w-xs border border-white/15 bg-black p-6 text-center"
            initial={{ y: 30, opacity: 0, scale: 0.96 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: 20, opacity: 0, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-red">
              18+
            </p>
            <h2
              id="age-gate-title"
              className="font-display mt-2 text-lg font-bold uppercase tracking-wide text-cream"
            >
              {almostThere ? "almost there" : "adults-only content ahead"}
            </h2>
            <p className="font-mono mt-2 text-xs leading-relaxed text-muted">
              you&apos;re about to leave this page for content intended
              for viewers 18 and older. confirm your age to continue.
            </p>

            {inApp ? (
              <>
                <a href={fanvueUrl} target="_blank" rel="noopener noreferrer" onClick={onInAppAttempt} className="font-mono mt-5 block w-full bg-red py-3.5 text-xs font-bold uppercase tracking-widest text-cream">
                  I&apos;m 18 or older — continue
                </a>

                <div className="mt-4 border border-white/15 bg-white/5 p-4 text-left">
                  <p className="font-mono text-center text-xs uppercase tracking-widest text-red">
                    if that opened inside instagram
                  </p>
                  <div className="mt-3 flex items-center gap-3">
                    <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center border border-white/15">
                      <DotsIcon />
                    </span>
                    <p className="font-mono text-xs text-cream/90">
                      Tap the <strong>&quot;•••&quot;</strong> icon in the top right
                    </p>
                  </div>
                  <div className="mt-2.5 flex items-center gap-3">
                    <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center border border-white/15">
                      <BrowserIcon />
                    </span>
                    <p className="font-mono text-xs text-cream/90">
                      Select <strong>&quot;Open in External Browser&quot;</strong>
                    </p>
                  </div>
                </div>

                <button onClick={onCancel} className="font-mono mt-3 w-full py-3 text-xs uppercase tracking-widest text-muted">
                  go back
                </button>
              </>
            ) : (
              <>
                <button onClick={onConfirm} className="font-mono mt-5 w-full bg-red py-3.5 text-xs font-bold uppercase tracking-widest text-cream">
                  I&apos;m 18 or older — continue
                </button>
                <button onClick={onCancel} className="font-mono mt-2 w-full py-3 text-xs uppercase tracking-widest text-muted">
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
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="2.4" strokeLinecap="round">
      <circle cx="5" cy="12" r="1.4" fill="var(--red)" stroke="none" />
      <circle cx="12" cy="12" r="1.4" fill="var(--red)" stroke="none" />
      <circle cx="19" cy="12" r="1.4" fill="var(--red)" stroke="none" />
    </svg>
  );
}

function BrowserIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="1.8">
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="M3 8.5h18" strokeLinecap="round" />
      <path d="M13.5 12.5h4.5v4.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M18 12.5l-5.5 5.5" strokeLinecap="round" />
    </svg>
  );
}
