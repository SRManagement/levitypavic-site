"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import Reveal from "@/components/Reveal";
import AgeGate from "@/components/AgeGate";
import ImageSlot from "@/components/ImageSlot";
import { openExternal } from "@/lib/browser";

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
    setTimeout(() => openExternal(LINKS.fanvue), 120);
  }

  return (
    <main className="relative flex w-full flex-col items-center bg-bg px-5 pb-24 pt-14">
      <AgeGate
        open={gateOpen}
        onConfirm={confirmFanvue}
        onCancel={() => setGateOpen(false)}
      />

      {/* intro */}
      <div className="w-full max-w-sm text-left">
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          className="font-mono text-[13px] leading-relaxed text-pink"
        >
          explore Levity&apos;s world — exclusive content, lifestyle
          updates, favorite links and more 💋
        </motion.p>
      </div>

      {/* unlock card + polaroid, stacked */}
      <div className="mt-8 flex w-full max-w-sm flex-col gap-8">
        <Reveal delay={0.05}>
          <button
            onClick={requestFanvue}
            className="group relative block aspect-[8/5] w-full overflow-hidden rounded-[24px] border border-white/10 text-left"
          >
            <div className="absolute inset-0 bg-surface">
              <ImageSlot
                src="/images/cover.jpg"
                alt="Levity Pavic"
                label="cover photo"
              />
            </div>
            <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-transparent" />
            <div className="absolute inset-0 flex flex-col justify-end p-5">
              <p className="glow-text font-ornate flex items-center gap-2 text-2xl font-bold italic tracking-tight">
                <LockIcon size={18} /> Private Access
              </p>
              <p className="mt-2 text-sm text-cream/90">
                exclusive content, BTS and more
              </p>
              <span className="glass-button mt-4 inline-flex w-fit items-center gap-2 rounded-full p-1.5 transition-transform group-active:scale-95">
                <span
                  className="rounded-full px-5 py-2 text-sm font-bold uppercase tracking-wide text-white"
                  style={{
                    background:
                      "linear-gradient(135deg, rgba(255,255,255,0.4), rgba(255,140,185,0.65))",
                  }}
                >
                  Unlock
                </span>
                <span className="text-base">💖</span>
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15">
                  <ArrowIcon color="#fff" />
                </span>
              </span>
            </div>
          </button>
        </Reveal>

        <Reveal delay={0.15}>
          <div className="polaroid-grid mx-auto w-[240px] rounded-[20px] p-2.5 shadow-[0_20px_50px_rgba(0,0,0,0.45)]">
            <PolaroidPhoto onClick={requestFanvue} />
            <div className="px-1.5 pb-1 pt-3">
              <p className="font-condensed text-xl text-pink">
                LEVITY PAVIC
              </p>
              <div className="mt-1 flex items-center justify-between">
                <p className="text-[11px] text-neutral-500">
                  model · creator · muse
                </p>
                <p className="font-mono text-[11px] text-neutral-400">2026</p>
              </div>
              <div className="mt-3 flex items-center gap-4 border-t border-neutral-200 pt-3">
                <button onClick={() => goSocial("instagram")} aria-label="instagram">
                  <InstagramIcon color="#ff4d79" />
                </button>
                <button onClick={() => goSocial("tiktok")} aria-label="tiktok">
                  <TikTokIcon color="#ff4d79" />
                </button>
                <button onClick={() => goSocial("snapchat")} aria-label="snapchat">
                  <SnapchatIcon color="#ff4d79" />
                </button>
              </div>
            </div>
          </div>
        </Reveal>
      </div>

      {/* link list */}
      <div className="mt-14 flex w-full max-w-sm flex-col gap-4">
        <LinkRow
          delay={0}
          label="instagram"
          sub="follow me here"
          image="/images/link-instagram.jpg"
          onClick={() => goSocial("instagram")}
        />
        <LinkRow
          delay={0.08}
          label="tiktok"
          sub="just having fun"
          image="/images/link-tiktok.jpg"
          onClick={() => goSocial("tiktok")}
        />
        <LinkRow
          delay={0.16}
          label="snapchat"
          sub="add me on snap!"
          image="/images/link-snapchat.jpg"
          onClick={() => goSocial("snapchat")}
        />
      </div>

      {/* feed strip */}
      <Reveal delay={0.1}>
        <div className="mt-16 w-full max-w-sm">
          <button
            onClick={() => goSocial("instagram")}
            className="mb-3 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-pink"
          >
            <InstagramIcon color="var(--pink)" size={16} /> current feed
          </button>
          <div className="grid grid-cols-3 gap-1.5">
            {Array.from({ length: 6 }).map((_, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className="aspect-square overflow-hidden rounded-md bg-surface"
              >
                <ImageSlot
                  src={`/images/feed-${i + 1}.jpg`}
                  alt={`feed photo ${i + 1}`}
                  label={`feed-${i + 1}.jpg`}
                />
              </motion.div>
            ))}
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.05}>
        <p className="mt-16 font-mono text-[11px] tracking-wide text-muted">
          @levitypavic
        </p>
      </Reveal>
    </main>
  );
}

function PolaroidPhoto({ onClick }: { onClick: () => void }) {
  const ref = useRef<HTMLButtonElement>(null);
  const [centered, setCentered] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setCentered(entry.isIntersecting),
      { rootMargin: "-40% 0px -40% 0px", threshold: 0 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <button
      ref={ref}
      onClick={onClick}
      className="group relative block aspect-square w-full overflow-hidden rounded-[14px] bg-surface-2 text-left"
    >
      <ImageSlot
        src="/images/portrait.jpg"
        alt="Levity Pavic portrait"
        label="portrait photo"
        className={`transition-[filter] duration-700 ease-out group-hover:grayscale-0 group-hover:saturate-125 ${
          centered ? "grayscale-0 saturate-125" : "grayscale"
        }`}
      />
      <div className="grain pointer-events-none absolute inset-0" />
    </button>
  );
}

function LinkRow({
  label,
  sub,
  onClick,
  delay,
  image,
}: {
  label: string;
  sub: string;
  onClick: () => void;
  delay: number;
  image: string;
}) {
  return (
    <Reveal delay={delay}>
      <button
        onClick={onClick}
        className="group flex w-full items-center gap-4 overflow-hidden rounded-[20px] border border-pink/25 bg-surface text-left transition-colors active:bg-surface-2"
      >
        <div className="h-[92px] w-[92px] flex-shrink-0 bg-surface-2">
          <ImageSlot src={image} alt={`${label} thumbnail`} label="photo" />
        </div>
        <div className="flex flex-1 items-center justify-between py-3 pr-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-pink">
              link:
            </p>
            <p className="font-ornate text-lg font-bold uppercase tracking-tight text-cream">
              {label}
            </p>
            <p className="mt-0.5 text-xs text-muted">{sub}</p>
          </div>
          <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full transition-transform group-active:scale-90"
            style={{ background: "var(--pink)" }}
          >
            <ArrowIcon />
          </span>
        </div>
      </button>
    </Reveal>
  );
}

function ArrowIcon({ color = "var(--bg)" }: { color?: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

function LockIcon({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="11" width="16" height="9" rx="2" />
      <path d="M8 11V7a4 4 0 1 1 8 0v4" />
    </svg>
  );
}

function InstagramIcon({ color = "#fff", size = 20 }: { color?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.7">
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.2" cy="6.8" r="1" fill={color} stroke="none" />
    </svg>
  );
}

function TikTokIcon({ color = "#fff" }: { color?: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.7">
      <path d="M14 4v9.5a3.5 3.5 0 1 1-3.5-3.5" />
      <path d="M14 4c.5 2.3 2 3.7 4.2 4" />
    </svg>
  );
}

function SnapchatIcon({ color = "#fff" }: { color?: string }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6">
      <path d="M12 4c3 0 4.5 2.2 4.5 5.3 0 .8-.05 1.5-.15 2.1.6.3 1.15.9 1.15 1.4 0 .7-1 1.4-1.9 1.7-.2.9-.5 1.3-.9 1.6.1.5.5 1 1.4 1.4.4.2.4.7 0 1-.6.5-1.6.7-2.4.7-.3.5-1 1.3-1.7 1.3s-1.4-.8-1.7-1.3c-.8 0-1.8-.2-2.4-.7-.4-.3-.4-.8 0-1 .9-.4 1.3-.9 1.4-1.4-.4-.3-.7-.7-.9-1.6-.9-.3-1.9-1-1.9-1.7 0-.5.55-1.1 1.15-1.4-.1-.6-.15-1.3-.15-2.1C7.5 6.2 9 4 12 4Z" />
    </svg>
  );
}
