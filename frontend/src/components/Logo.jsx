import { Terminal } from "lucide-react";

// variant: "ti" (admin) | "tecnico" (public)
export const Logo = ({ variant = "tecnico", className = "" }) => {
  const sub = variant === "ti" ? "TI" : "Técnico";
  return (
    <div className={`flex items-center gap-3 ${className}`} data-testid={`logo-${variant}`}>
      <div className="relative flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 ring-1 ring-emerald-500/40">
        <Terminal className="h-5 w-5 text-emerald-400" strokeWidth={2.4} />
        <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_2px_rgba(16,185,129,0.6)]" />
      </div>
      <div className="leading-none">
        <div className="font-display text-lg font-extrabold tracking-tight text-emerald-50">
          grau <span className="text-emerald-400">{sub}</span>
        </div>
        <div className="font-mono-tech text-[10px] uppercase tracking-[0.2em] text-emerald-500/70">
          Suporte de TI
        </div>
      </div>
    </div>
  );
};
