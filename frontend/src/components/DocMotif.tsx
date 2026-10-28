/** Decorative document schematic: linework only, implies no operation was performed. */
export default function DocMotif({ scanning = false, className = "" }: { scanning?: boolean; className?: string }) {
  return (
    <div className={`relative ${className}`} aria-hidden>
      <svg viewBox="0 0 220 280" className="h-full w-full" fill="none">
        <path d="M24 12h128l44 44v212a8 8 0 0 1-8 8H24a8 8 0 0 1-8-8V20a8 8 0 0 1 8-8z" className="stroke-current" strokeWidth="1.5" />
        <path d="M152 12v36a8 8 0 0 0 8 8h36" className="stroke-current" strokeWidth="1.5" />
        {[76, 96, 116, 136, 156].map((y, i) => <line key={y} x1="40" y1={y} x2={i === 1 ? 128 : i === 3 ? 150 : 176} y2={y} className="stroke-current" strokeWidth="1.5" strokeOpacity={0.55} />)}
        <rect x="40" y="178" width="136" height="18" rx="3" className="stroke-current" strokeWidth="1.2" strokeOpacity={0.4} />
        <rect x="118" y="181" width="52" height="12" rx="2" className="fill-amber-400/25 stroke-amber-400" strokeWidth="1.2" />
        <line x1="40" y1="214" x2="112" y2="214" className="stroke-current" strokeWidth="1.5" strokeOpacity={0.55} />
        <line x1="40" y1="234" x2="164" y2="234" className="stroke-current" strokeWidth="1.5" strokeOpacity={0.55} />
        <text x="136" y="252" className="fill-current font-mono" fontSize="9" opacity="0.6">sha256</text>
      </svg>
      {scanning && <div className="absolute left-[8%] right-[8%] h-px animate-scanline bg-accent " />}
    </div>
  );
}