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
  const [isPlaying, setIsPlaying] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    el.muted = true;

    function tryPlay() {
      el?.play().catch(() => {});
    }

    // Only once this actually fires do we reveal the video — this is
    // the real guarantee against any native "paused"/"tap to play" UI
    // ever being visible (e.g. iOS Low Power Mode): the video element
    // stays invisible, poster image shown in its place, until genuine
    // playback is confirmed. Nothing to see means nothing to hide.
    function handlePlaying() {
      setIsPlaying(true);
    }

    el.addEventListener("playing", handlePlaying);
    tryPlay();
    el.addEventListener("loadeddata", tryPlay);
    el.addEventListener("canplay", tryPlay);

    // Safety net: the very first real interaction anywhere on the page
    // always unlocks playback, even under Low Power Mode.
    function retryOnFirstTouch() {
      tryPlay();
      document.removeEventListener("touchstart", retryOnFirstTouch);
      document.removeEventListener("click", retryOnFirstTouch);
    }
    document.addEventListener("touchstart", retryOnFirstTouch, { once: true });
    document.addEventListener("click", retryOnFirstTouch, { once: true });

    return () => {
      el.removeEventListener("playing", handlePlaying);
      el.removeEventListener("loadeddata", tryPlay);
      el.removeEventListener("canplay", tryPlay);
      document.removeEventListener("touchstart", retryOnFirstTouch);
      document.removeEventListener("click", retryOnFirstTouch);
    };
  }, [videoSrc]);

  if (videoFailed) {
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

  return (
    <div className={`relative h-full w-full ${className}`}>
      {/* Poster image — fully visible until playback is confirmed,
          fades out once the real video takes over. */}
      {!posterFailed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={posterSrc}
          alt="Levity Pavic"
          onError={() => setPosterFailed(true)}
          className="absolute inset-0 h-full w-full object-cover transition-opacity duration-500"
          style={{ opacity: isPlaying ? 0 : 1 }}
        />
      )}
      <video
        ref={videoRef}
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        onError={() => setVideoFailed(true)}
        className="absolute inset-0 h-full w-full object-cover transition-opacity duration-500"
        style={{ opacity: isPlaying ? 1 : 0 }}
      >
        <source src={videoSrc} type="video/mp4" />
      </video>
    </div>
  );
}
