"use client";

import { useEffect, useRef, useState } from "react";

export default function VideoSlot({
  videoSrc,
  posterSrc,
  className = "",
}: {
  videoSrc: string;
  posterSrc: string;
  className?: string;
}) {
  const [videoFailed, setVideoFailed] = useState(false);
  const [posterFailed, setPosterFailed] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    // iOS Safari requires the video to be genuinely muted at the moment
    // autoplay is attempted, or it blocks autoplay and shows a manual
    // play prompt instead. React's JSX `muted` attribute doesn't always
    // reliably reach the real DOM property in time — setting it directly
    // here, then explicitly calling play(), is the reliable fix.
    el.muted = true;
    el.play().catch(() => {
      // Autoplay was blocked for some other reason (rare, but possible
      // depending on browser/data-saver settings) — the poster image
      // stays visible in that case, which is a reasonable fallback.
    });
  }, [videoSrc]);

  if (!videoFailed) {
    return (
      <video
        ref={videoRef}
        autoPlay
        muted
        loop
        playsInline
        poster={posterSrc}
        onError={() => setVideoFailed(true)}
        className={`h-full w-full object-cover ${className}`}
      >
        <source src={videoSrc} type="video/mp4" />
      </video>
    );
  }

  if (!posterFailed) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={posterSrc}
        alt="Levity Pavic"
        onError={() => setPosterFailed(true)}
        className={`h-full w-full object-cover ${className}`}
      />
    );
  }

  return (
    <div className={`flex items-center justify-center bg-black ${className}`}>
      <span className="px-4 text-center text-[10px] leading-relaxed text-muted">
        add background video to /public/videos
        <br />
        or photo to /public/images
      </span>
    </div>
  );
}
