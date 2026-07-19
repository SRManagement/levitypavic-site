"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence, useMotionValue, useTransform, animate } from "framer-motion";
import AgeGate from "@/components/AgeGate";
import VideoSlot from "@/components/VideoSlot";
import ImageSlot from "@/components/ImageSlot";
import { openExternal, isInAppBrowser } from "@/lib/browser";

type Platform = "fanvue" | "instagram" | "tiktok" | "snapchat";

const LINKS: Record<Platform, string> = {
  fanvue: "https://www.fanvue.com/sparedbytheking",
  instagram: "https://www.instagram.com/SPAREDBYTHEKING/",
  tiktok: "https://www.tiktok.com/@sparedbytheking",
  snapchat: "https://www.snapchat.com/add/levitypavic",
};

function track(platform: Platform) {
  try {
    navigator.sendBeacon(
      "/api/click",
      new Blob([JSON.stringify({ platform })], { type: "application/json" })
    );
  } catch {
    fetch("/api/click", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform }),
      keepalive: true,
    }).catch(() => {});
  }
}

export default function Home() {
  const [gateOpen, setGateOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [contactOpen, setContactOpen] = useState(false);
  const [showIntro, setShowIntro] = useState(true);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("go") === "fanvue" && !isInAppBrowser()) {
      window.history.replaceState(null, "", window.location.pathname);
      setGateOpen(true);
    }
  }, []);

  function goSocial(platform: Exclude<Platform, "fanvue">) {
    track(platform);
    openExternal(LINKS[platform]);
  }

  function requestFanvue() {
    setGateOpen(true);

    if (isInAppBrowser()) {
      track("fanvue");
      window.history.replaceState(null, "", "?go=fanvue");
    }
  }

  function confirmFanvue() {
    track("fanvue");
    setGateOpen(false);
    openExternal(LINKS.fanvue);
  }

  return (
    <main className="relative h-[100dvh] w-full overflow-hidden bg-bg">
      {showIntro && (
        <IntroSequence
          onReveal={() => setRevealed(true)}
          onDone={() => setShowIntro(false)}
        />
      )}

      <AgeGate
        open={gateOpen}
        onConfirm={confirmFanvue}
        onCancel={() => setGateOpen(false)}
      />
      <AboutPanel open={aboutOpen} onClose={() => setAboutOpen(false)} />
      <ContactPopup open={contactOpen} onClose={() => setContactOpen(false)} />

      {/* Background media */}
      <div className="absolute inset-0">
        <VideoSlot videoSrc="/videos/hero-bg.mp4" posterSrc="/images/hero-bg.jpg" />
        <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-black/20 to-black/80" />
      </div>

      {/* Foreground layout */}
      <div className="relative z-10 flex h-full w-full flex-col justify-between px-5 py-6">
        <div className="flex w-full items-center justify-between">
          <motion.button
            onClick={() => setAboutOpen(true)}
            initial={{ x: "-120%", opacity: 0 }}
            animate={revealed ? { x: 0, opacity: 1 } : {}}
            transition={{ type: "spring", stiffness: 480, damping: 26 }}
            className="font-display text-xs font-medium uppercase tracking-widest text-cream active:opacity-60"
          >
            About Me
          </motion.button>
          <motion.button
            onClick={() => setContactOpen(true)}
            initial={{ x: "120%", opacity: 0 }}
            animate={revealed ? { x: 0, opacity: 1 } : {}}
            transition={{ type: "spring", stiffness: 480, damping: 26 }}
            className="font-display text-xs font-medium uppercase tracking-widest text-cream active:opacity-60"
          >
            Contact
          </motion.button>
        </div>

        <div className="flex flex-1 items-center justify-center">
          <Wordmark />
        </div>

        <motion.div
          initial={{ y: "140%", opacity: 0 }}
          animate={revealed ? { y: 0, opacity: 1 } : {}}
          transition={{ type: "spring", stiffness: 420, damping: 30 }}
          className="flex flex-col items-center pb-2"
        >
          <p className="font-mono mb-4 text-[11px] uppercase tracking-[0.35em] text-muted">
            All My Links
          </p>
          <div className="flex flex-col items-center">
            <LinkWord label="Instagram" onClick={() => goSocial("instagram")} />
            <LinkWord label="TikTok" onClick={() => goSocial("tiktok")} />
            <LinkWord label="Snapchat" onClick={() => goSocial("snapchat")} />
            <LinkWord label="Unlock" onClick={requestFanvue} accent />
          </div>
        </motion.div>
      </div>
    </main>
  );
}

function Wordmark() {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <h1 className="blend-invert font-display w-full text-center text-[22vw] font-black uppercase leading-[0.85] text-cream sm:text-[16vw]">
        Levity
      </h1>
    );
  }

  return (
    <img
      src="/images/levity-wordmark.png"
      alt="Levity"
      onError={() => setFailed(true)}
      className="blend-invert w-[85vw] max-w-2xl"
    />
  );
}

function IntroSequence({
  onReveal,
  onDone,
}: {
  onReveal: () => void;
  onDone: () => void;
}) {
  const wallProgress = useMotionValue(0); // 0 -> 100, drives wall height AND the text color-flip line together
  const containerOpacity = useMotionValue(1);

  const wallHeight = useTransform(wallProgress, (p) => `${p}%`);
  // The white (flipped) text copy is only visible below the current wall
  // line — same percentage, same viewport-relative coordinate space as
  // the wall itself, so the flip always lines up exactly with the wall's
  // edge, never drifts out of sync.
  const whiteClip = useTransform(wallProgress, (p) => `inset(${100 - p}% 0 0 0)`);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      // Phase 1: text slides up into place (handled by its own
      // initial/animate below) — just wait for it to settle.
      await new Promise((r) => setTimeout(r, 550));
      if (cancelled) return;

      // Phase 2: black wall rises from the bottom, text flips to white
      // exactly where the wall's edge currently is.
      await animate(wallProgress, 100, {
        duration: 0.7,
        ease: [0.16, 1, 0.3, 1],
      });
      if (cancelled) return;

      // Phase 3: trigger the rest of the page's content to snap in
      // (About Me / Contact / bottom links), then fade the black away
      // to reveal the real video background underneath.
      onReveal();
      await animate(containerOpacity, 0, {
        duration: 0.5,
        ease: "easeInOut",
      });
      if (cancelled) return;

      onDone();
    }

    run();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <motion.div
      style={{ opacity: containerOpacity }}
      className="fixed inset-0 z-[95] overflow-hidden bg-red"
    >
      {/* Rising black wall, anchored to the bottom */}
      <motion.div
        style={{ height: wallHeight }}
        className="absolute inset-x-0 bottom-0 bg-black"
      />

      {/* Black wordmark — visible above the wall line, against red */}
      <motion.img
        src="/images/levity-wordmark.png"
        alt=""
        aria-hidden="true"
        initial={{ y: "140%" }}
        animate={{ y: 0 }}
        transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        className="absolute inset-0 m-auto h-fit w-[85vw] max-w-2xl"
        style={{ filter: "brightness(0)" }}
      />

      {/* White wordmark — only revealed below the wall line, matching
          the wall's current height exactly */}
      <motion.img
        src="/images/levity-wordmark.png"
        alt=""
        aria-hidden="true"
        initial={{ y: "140%" }}
        animate={{ y: 0 }}
        transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
        className="absolute inset-0 m-auto h-fit w-[85vw] max-w-2xl"
        style={{ clipPath: whiteClip }}
      />
    </motion.div>
  );
}

function LinkWord({
  label,
  onClick,
  accent = false,
}: {
  label: string;
  onClick: () => void;
  accent?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`font-display ease-premium text-4xl font-bold uppercase leading-[1.05] tracking-tight transition-colors sm:text-5xl ${
        accent ? "text-red" : "text-cream active:text-red"
      }`}
    >
      {label}
    </button>
  );
}

function AboutPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-y-0 right-0 z-[60] w-[92%] max-w-lg overflow-y-auto bg-red px-6 pb-10 pt-6"
        >
          <button
            onClick={onClose}
            className="font-display text-sm text-black active:opacity-60"
          >
            [ &times; ]
          </button>

          <h2 className="font-display mt-6 text-5xl font-black uppercase leading-[0.95] text-black">
            Levity
            <br />
            Pavic
          </h2>

          <div className="mt-8 aspect-[3/4] w-full overflow-hidden bg-black/20">
            <ImageSlot
              src="/images/about-portrait.jpg"
              alt="Levity Pavic"
              label="portrait photo"
            />
          </div>

          <p className="font-display mt-8 text-base leading-relaxed text-black">
            Born and raised in Brooklyn and now living in SoHo, I am a
            21-year-old former professional K1 kickboxer who translates the
            rigorous discipline of elite athletics into everything I do.
            Having competed and won at both the amateur and professional
            levels of my sport, I maintain a deep connection to athletic
            analysis and high-level conditioning, structuring my daily life
            around intensive training.
          </p>
          <p className="font-display mt-4 text-base leading-relaxed text-black">
            Beyond the gym, I bring a sharp, analytical focus to my personal
            pursuits. I am a dedicated motorcyclist with a strong command of
            mechanical engineering, an avid follower of modern tattoo
            artistry and technique, and a connoisseur of underground
            electronic music and cinema. Driven by direct communication and
            a focus on precision, I am currently leveraging my competitive
            background to build new professional avenues in New York City.
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ContactPopup({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="w-full max-w-xs border border-white/15 bg-black p-6 text-center"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="font-display text-lg font-bold uppercase text-cream">
              Get in touch
            </p>
            <p className="font-mono mt-2 text-xs leading-relaxed text-muted">
              the fastest way to reach me is a DM on Instagram.
            </p>
            <button
              onClick={() => {
                track("instagram");
                openExternal(LINKS.instagram);
              }}
              className="font-mono mt-5 w-full bg-red py-3.5 text-xs font-bold uppercase tracking-widest text-cream"
            >
              Message on Instagram
            </button>
            <button
              onClick={onClose}
              className="font-mono mt-2 w-full py-3 text-xs uppercase tracking-widest text-muted"
            >
              close
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
