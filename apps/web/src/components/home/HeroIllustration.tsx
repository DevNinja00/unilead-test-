export default function HeroIllustration() {
  return (
    <svg
      viewBox="0 0 480 440"
      className="hero-illustration"
      role="img"
      aria-label="Illustration of a learning dashboard with progress and AI coaching"
    >
      <defs>
        <linearGradient id="hi-blob" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#eaefff" />
          <stop offset="100%" stopColor="#dfe6ff" />
        </linearGradient>
        <linearGradient id="hi-ring" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2952e3" />
          <stop offset="100%" stopColor="#5b7cf5" />
        </linearGradient>
      </defs>

      {/* backdrop blob */}
      <path
        d="M240 20c92 0 180 52 200 140 18 82-30 160-118 196-84 34-186 18-232-56C42 232 30 140 84 78 126 30 178 20 240 20Z"
        fill="url(#hi-blob)"
      />

      {/* main card: lesson / competency progress */}
      <g transform="translate(58 96)">
        <rect width="256" height="176" rx="20" fill="#ffffff" />
        <rect width="256" height="176" rx="20" fill="none" stroke="#e6e8ee" strokeWidth="1.5" />
        <rect x="24" y="28" width="120" height="12" rx="6" fill="#14181f" opacity="0.85" />
        <rect x="24" y="48" width="80" height="9" rx="4.5" fill="#93989f" />

        <rect x="24" y="84" width="208" height="8" rx="4" fill="#eef0f4" />
        <rect x="24" y="84" width="146" height="8" rx="4" fill="url(#hi-ring)" />

        <g transform="translate(24 110)">
          <circle cx="10" cy="10" r="10" fill="#e6f7ef" />
          <path d="M6 10l3 3 5-6" stroke="#22a06b" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          <rect x="28" y="5" width="110" height="10" rx="5" fill="#f1f2f5" />
        </g>
        <g transform="translate(24 132)">
          <circle cx="10" cy="10" r="10" fill="#fff6e0" />
          <circle cx="10" cy="10" r="4" fill="#d99a1f" />
          <rect x="28" y="5" width="90" height="10" rx="5" fill="#f1f2f5" />
        </g>
      </g>

      {/* floating AI coach bubble */}
      <g transform="translate(300 42)">
        <rect width="150" height="86" rx="18" fill="#2952e3" />
        <rect x="18" y="20" width="90" height="9" rx="4.5" fill="#ffffff" opacity="0.92" />
        <rect x="18" y="38" width="114" height="9" rx="4.5" fill="#ffffff" opacity="0.6" />
        <rect x="18" y="56" width="66" height="9" rx="4.5" fill="#ffffff" opacity="0.6" />
        <path d="M28 86l-14 20 26-12z" fill="#2952e3" />
      </g>

      {/* competency badge */}
      <g transform="translate(300 268)">
        <circle cx="46" cy="46" r="46" fill="#ffffff" stroke="#e6e8ee" strokeWidth="1.5" />
        <circle cx="46" cy="46" r="34" fill="none" stroke="#eef0f4" strokeWidth="8" />
        <circle
          cx="46"
          cy="46"
          r="34"
          fill="none"
          stroke="url(#hi-ring)"
          strokeWidth="8"
          strokeDasharray="176 214"
          strokeLinecap="round"
          transform="rotate(-90 46 46)"
        />
        <path d="M34 46l8 8 16-18" stroke="#2952e3" strokeWidth="3.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>

      {/* small orange accent chip */}
      <g transform="translate(40 320)">
        <rect width="118" height="60" rx="16" fill="#ffffff" stroke="#e6e8ee" strokeWidth="1.5" />
        <circle cx="30" cy="30" r="14" fill="#fff1e6" />
        <path d="M24 30l4 4 8-9" stroke="#ff8a3d" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="54" y="20" width="48" height="8" rx="4" fill="#14181f" opacity="0.75" />
        <rect x="54" y="34" width="34" height="7" rx="3.5" fill="#93989f" />
      </g>
    </svg>
  );
}
