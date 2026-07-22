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
              adults-only content ahead
            </h2>
            <p className="font-mono mt-2 text-xs leading-relaxed text-muted">
              you&apos;re about to leave this page for content intended
              for viewers 18 and older. confirm your age to continue.
            </p>

            <button
              onClick={onConfirm}
              className="font-mono mt-5 w-full bg-red py-3.5 text-xs font-bold uppercase tracking-widest text-cream"
            >
              I&apos;m 18 or older — continue
            </button>
            <button
              onClick={onCancel}
              className="font-mono mt-2 w-full py-3 text-xs uppercase tracking-widest text-muted"
            >
              go back
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
