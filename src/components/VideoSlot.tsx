"use client";

import { useState } from "react";

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

  if (!videoFailed) {
    return (
      <video
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
