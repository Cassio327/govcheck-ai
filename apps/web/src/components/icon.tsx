import type { SVGProps } from "react";

type IconName = "upload" | "file" | "send" | "download" | "info" | "lock" | "menu" | "chevron";

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>
      {name === "upload" ? <><path {...common} d="M12 16V3m0 0L7.5 7.5M12 3l4.5 4.5"/><path {...common} d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/></> : null}
      {name === "file" ? <><path {...common} d="M6 2.8h8l4 4V21H6z"/><path {...common} d="M14 2.8V7h4"/></> : null}
      {name === "send" ? <path {...common} d="M21 3L9.4 14.6M21 3l-7 18-4.6-6.4L3 10z"/> : null}
      {name === "download" ? <><path {...common} d="M12 3v12m0 0l4-4m-4 4l-4-4"/><path {...common} d="M4 19v2h16v-2"/></> : null}
      {name === "info" ? <><circle {...common} cx="12" cy="12" r="9"/><path {...common} d="M12 10v6m0-9h.01"/></> : null}
      {name === "lock" ? <><rect {...common} x="5" y="10" width="14" height="11" rx="2"/><path {...common} d="M8 10V7a4 4 0 0 1 8 0v3"/></> : null}
      {name === "menu" ? <path {...common} d="M4 7h16M4 12h16M4 17h16"/> : null}
      {name === "chevron" ? <path {...common} d="M7 10l5 5 5-5"/> : null}
    </svg>
  );
}
