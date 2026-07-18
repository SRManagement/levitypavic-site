"use client";

import { AnimatePresence, motion } from "framer-motion";

export default function AgeGate({
  open,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
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
            <p className="mt-2 text-sm leading-relaxed text-muted">
              you&apos;re about to leave this page for content intended for
              viewers 18 and older. confirm your age to continue.
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
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
