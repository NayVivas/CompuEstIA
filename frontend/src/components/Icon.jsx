export default function Icon({ name, size = 20 }) {
  const commonProps = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };

  const paths = {
    activity: (
      <>
        <path d="M3 12h4l3-8 4 16 3-8h4" />
      </>
    ),

    arrowRight: (
      <>
        <path d="M5 12h13" />
        <path d="m13 6 6 6-6 6" />
      </>
    ),

    arrowUp: (
      <>
        <path d="M12 19V5" />
        <path d="m6 11 6-6 6 6" />
      </>
    ),

    barChart: (
      <>
        <path d="M4 19V9" />
        <path d="M10 19V5" />
        <path d="M16 19v-7" />
        <path d="M22 19V3" />
      </>
    ),

    building: (
      <>
        <path d="M4 21V5l8-3 8 3v16" />
        <path d="M9 21v-4h6v4" />
        <path d="M8 7h1M15 7h1M8 11h1M15 11h1" />
      </>
    ),

    check: <path d="m5 12 4 4L19 6" />,

    chevronDown: <path d="m6 9 6 6 6-6" />,

    clock: (
      <>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v4l2.5 2" />
      </>
    ),

    dashboard: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),

    file: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M8 13h8M8 17h5" />
      </>
    ),

    folder: (
      <>
        <path d="M3 6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z" />
      </>
    ),

    layers: (
      <>
        <path d="m12 3 9 5-9 5-9-5 9-5Z" />
        <path d="m3 12 9 5 9-5" />
        <path d="m3 16 9 5 9-5" />
      </>
    ),

    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      </>
    ),

    plus: (
      <>
        <path d="M12 5v14M5 12h14" />
      </>
    ),

    refresh: (
      <>
        <path d="M20 11a8.1 8.1 0 0 0-14.8-3L3 11" />
        <path d="M3 6v5h5" />
        <path d="M4 13a8.1 8.1 0 0 0 14.8 3L21 13" />
        <path d="M21 18v-5h-5" />
      </>
    ),

    report: (
      <>
        <path d="M6 3h9l4 4v14H6z" />
        <path d="M15 3v5h5" />
        <path d="M9 13h6M9 17h6M9 9h2" />
      </>
    ),

    scan: (
      <>
        <path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3" />
        <path d="M7 12h10M12 7v10" />
      </>
    ),

    shield: (
      <>
        <path d="M12 3 20 6v5c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10V6z" />
        <path d="m8.5 12 2.2 2.2 4.8-5" />
      </>
    ),

    upload: (
      <>
        <path d="M12 16V4" />
        <path d="m7 9 5-5 5 5" />
        <path d="M5 20h14" />
      </>
    ),

    x: (
      <>
        <path d="M6 6l12 12M18 6 6 18" />
      </>
    ),
  };

  return <svg {...commonProps}>{paths[name] || paths.file}</svg>;
}