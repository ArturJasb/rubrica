export default function Logo() {
  return (
    <span className="logo">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden>
        <rect x="2" y="2" width="28" height="28" rx="8" fill="var(--accent)" />
        <path d="M9 11h14M9 16h10M9 21h7" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
        <circle cx="23" cy="21" r="2.4" fill="#fff" />
      </svg>
      Rubrica
    </span>
  );
}
