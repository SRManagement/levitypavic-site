"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence, useMotionValue, useTransform, animate } from "framer-motion";
import AgeGate from "@/components/AgeGate";
import VideoSlot from "@/components/VideoSlot";
import ImageSlot from "@/components/ImageSlot";
import { openExternal, isInAppBrowser } from "@/lib/browser";

type Platform = "fanvue" | "instagram" | "tiktok" | "snapchat" | "telegram";

const LINKS: Record<Platform, string> = {
  fanvue: "https://www.fanvue.com/sparedbytheking",
  instagram: "https://www.instagram.com/SPAREDBYTHEKING/",
  tiktok: "https://www.tiktok.com/@sparedbytheking",
  snapchat: "https://www.snapchat.com/add/levitypavic",
  telegram: "https://t.me/levitypavic", // TODO: swap in the real channel URL
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
  const [inApp, setInApp] = useState(false);
  const [checkedInApp, setCheckedInApp] = useState(false);

  useEffect(() => {
    setInApp(isInAppBrowser());
    setCheckedInApp(true);
  }, []);

  function goSocial(platform: Exclude<Platform, "fanvue">) {
    track(platform);
    openExternal(LINKS[platform]);
  }

  function requestFanvue() {
    setGateOpen(true);
  }

  function confirmFanvue() {
    track("fanvue");
    setGateOpen(false);
    openExternal(LINKS.fanvue);
  }

  return (
    <main className="relative h-[100dvh] w-full overflow-hidden bg-bg">
      {/* Preloads the About Me portrait in the background on first page
          load, so it's already cached by the time someone taps About Me
          — otherwise the browser only starts fetching it at that moment,
          which is what caused the slow first-open on a cold cache. */}
      <link rel="preload" as="image" href="/images/about-portrait.jpg" />

      {/* Solid black mask, covers everything until we know for certain
          whether to show the ExitInstagramGate or the intro — prevents
          either from starting prematurely. Appears/disappears instantly,
          no transition, so there's nothing left to overlap or bleed
          through with anything underneath. */}
      {!checkedInApp && <div className="fixed inset-0 z-[110] bg-black" />}

      {/* Mandatory gate — shown immediately, before anything else, only
          when inside an in-app browser (Instagram etc). No dismiss
          option by design: the person either continues out to their
          real browser or leaves. Everyone who reaches the rest of the
          site (including the age gate below) is guaranteed to already
          be in a real browser, which is what lets AgeGate stay simple —
          no more in-app-specific branching needed there. */}
      {checkedInApp && inApp && <ExitInstagramGate />}

      {checkedInApp && !inApp && showIntro && (
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
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/70 via-black/20 to-black/80" />
      </div>

      {/* Wordmark — positioned against the full screen (matching <main>,
          which is h-[100dvh]) so its coordinate system is identical to
          the intro overlay's (also full-screen via fixed inset-0). If
          this were nested inside the flex layout below instead, "20%
          from the top" would mean two different actual pixel positions
          in each case — which is exactly what caused the jump/relocate
          bug. Kept as a sibling, not a child, of the flex content. */}
      <div className="absolute left-1/2 top-[20%] z-10 w-[85vw] max-w-2xl -translate-x-1/2 -translate-y-1/2">
        <Wordmark />
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

        <div className="flex-1" />

        <motion.div
          initial={{ y: "140%", opacity: 0 }}
          animate={revealed ? { y: 0, opacity: 1 } : {}}
          transition={{ type: "spring", stiffness: 420, damping: 30 }}
          className="flex flex-col items-center pb-2"
        >
          <p className="font-mono mb-4 text-[11px] uppercase tracking-[0.35em] text-[#b8b8b8]">
            All My Links
          </p>
          <div className="flex flex-col items-center">
            <LinkWord label="Exclusive Content" onClick={requestFanvue} accent />
            <LinkWord label="Telegram" onClick={() => goSocial("telegram")} />
            <LinkWord label="Instagram" onClick={() => goSocial("instagram")} />
            <LinkWord label="Snapchat" onClick={() => goSocial("snapchat")} />
            <LinkWord label="TikTok" onClick={() => goSocial("tiktok")} />
          </div>
        </motion.div>
      </div>
    </main>
  );
}

function ExitInstagramGate() {
  return (
    <div className="fixed inset-0 z-[100] overflow-hidden bg-black">
      {/* Blurred hero video playing behind the prompt — same source used
          on the main site, just heavily blurred here to create mystery
          rather than reveal anything clearly. Plain autoplay, nothing
          fancy — a prior attempt at skipping the first couple seconds
          caused a black screen (removing autoPlay also stopped the
          browser from eagerly downloading the video at all), so this
          stays simple and just works. */}
      <video
        autoPlay
        muted
        loop
        playsInline
        poster="/images/hero-bg.jpg"
        className="absolute inset-0 h-full w-full scale-110 object-cover blur-lg"
      >
        <source src="/videos/hero-bg.mp4" type="video/mp4" />
      </video>
      <div className="absolute inset-0 bg-black/70" />

      {/* No button, no close, no way to dismiss — the person either
          follows these steps to escape Instagram's browser, or closes
          the link entirely. Nothing in between. */}
      <div className="relative z-10 flex h-full flex-col items-center justify-center px-6 text-center">
        <h1 className="font-display text-xl font-bold uppercase leading-snug text-cream">
          open in browser
        </h1>

        <div className="mt-6 w-full max-w-xs border border-white/15 bg-black/60 p-4 text-left backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center border border-white/15">
              <DotsIcon />
            </span>
            <p className="font-mono text-xs text-cream/90">
              Tap the <strong>&quot;•••&quot;</strong> icon in the top right
            </p>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center border border-white/15">
              <BrowserIcon />
            </span>
            <p className="font-mono text-xs text-cream/90">
              Select <strong>&quot;Open in External Browser&quot;</strong>
            </p>
          </div>
        </div>
      </div>
    </div>
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
      className="blend-invert w-full"
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
    <div className="fixed inset-0 z-[95] overflow-hidden">
      {/* Red background + rising black wall — this group is the ONLY
          thing that fades at the end. */}
      <motion.div
        style={{ opacity: containerOpacity }}
        className="absolute inset-0 bg-red"
      >
        <motion.div
          style={{ height: wallHeight }}
          className="absolute inset-x-0 bottom-0 bg-black"
        />
      </motion.div>

      {/* Wordmark — positioned to match its exact final resting spot
          (4/5 up the screen), so there's zero jump when this hands off
          to the real page's wordmark underneath. Slides up once on
          entry, then stays completely static — never tied to the
          background fade above. */}
      <div className="absolute left-1/2 top-[20%] w-[85vw] max-w-2xl -translate-x-1/2 -translate-y-1/2">
        {/* Black copy — visible above the wall line, against red */}
        <motion.img
          src="/images/levity-wordmark.png"
          alt=""
          aria-hidden="true"
          initial={{ y: "140%" }}
          animate={{ y: 0 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          className="w-full"
          style={{ filter: "brightness(0)" }}
        />
        {/* White copy — only revealed below the wall line, matching the
            wall's current height exactly */}
        <motion.img
          src="/images/levity-wordmark.png"
          alt=""
          aria-hidden="true"
          initial={{ y: "140%" }}
          animate={{ y: 0 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          className="absolute inset-0 w-full"
          style={{ clipPath: whiteClip }}
        />
      </div>
    </div>
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
      className={`font-display ease-premium text-3xl font-bold uppercase leading-[1.05] tracking-tight transition-colors sm:text-5xl ${
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
        <>
          {/* Full-screen tap-catcher, sits behind the panel — covers the
              sliver of background still visible on the left while the
              panel is open, so a tap there also closes it. */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[59]"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            onClick={onClose}
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
              Pavić
            </h2>

            <div className="mt-8 aspect-[3/4] w-3/5 max-w-[260px] overflow-hidden bg-black/20">
              <ImageSlot
                src="/images/about-portrait.jpg"
                alt="Levity Pavic"
                label="portrait photo"
              />
            </div>

            <p className="font-hanken mt-8 text-base leading-relaxed text-black">
              Born and raised in Brooklyn and now living in SoHo, NYC. I am a
              21-year-old former professional K1 kickboxer who translates the
              rigorous discipline of elite athletics into everything I do.
              Having competed and won at both the amateur and professional
              levels of my sport, I maintain a deep connection to athletic
              analysis and high-level conditioning, structuring my daily life
              around intensive training.
            </p>
            <p className="font-hanken mt-4 text-base leading-relaxed text-black">
              Beyond the gym, I bring a sharp, analytical focus to my personal
              pursuits. I am a dedicated motorcyclist with a strong command of
              mechanical engineering, an avid follower of modern tattoo
              artistry and technique, and a connoisseur of underground
              electronic music and cinema. Driven by direct communication and
              a focus on precision, I am currently leveraging my competitive
              background to build new professional avenues in New York City.
            </p>
          </motion.div>
        </>
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
            onClick={onClose}
            className="relative w-full max-w-xs border border-white/15 bg-black p-6 pt-10 text-center"
          >
            <button
              onClick={onClose}
              aria-label="close"
              className="absolute left-1/2 top-3 flex h-7 w-7 -translate-x-1/2 items-center justify-center rounded-full border border-white/25 text-cream"
            >
              <span className="text-xs leading-none">&times;</span>
            </button>

            <p className="font-display text-lg font-bold uppercase text-cream">
              Get in touch
            </p>
            <p className="font-mono mt-3 text-xs leading-relaxed text-muted">
              Business inquiries are handled exclusively through Instagram
              DM. Want to get to know me on a more personal level?
              That&apos;s exactly what the{" "}
              <span className="text-red">Exclusive Content</span> page is
              for, see you there!
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
