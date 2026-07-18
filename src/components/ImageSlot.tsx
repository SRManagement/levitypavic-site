"use client";

import { useState } from "react";

export default function ImageSlot({
  src,
  alt,
  label,
  className = "",
}: {
  src: string;
  alt: string;
  label: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className={`flex items-center justify-center bg-surface-2 ${className}`}
      >
        <span className="px-3 text-center text-[10px] leading-relaxed text-muted">
          {label}
          <br />
          add to /public/images
        </span>
      </div>
    );
  }

  // eslint-disable-next-line @next/next/no-img-element
  return (
    <img
      src={src}
      alt={alt}
      onError={() => setFailed(true)}
      className={`h-full w-full object-cover ${className}`}
    />
  );
}
