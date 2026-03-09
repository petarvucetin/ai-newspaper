interface SearchBarProps {
  value: string
  onChange: (value: string) => void
}

export function SearchBar({ value, onChange }: SearchBarProps) {
  return (
    <input
      type="search"
      placeholder="Search articles..."
      autoComplete="off"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="ml-auto rounded-full transition-all"
      style={{
        padding: "0.3rem 0.7rem",
        border: "1px solid var(--rule)",
        background: "var(--cream)",
        fontFamily: "var(--font-sans)",
        fontSize: "0.78rem",
        color: "var(--ink)",
        width: "180px",
        outline: "none",
      }}
      onFocus={(e) => (e.currentTarget.style.width = "240px")}
      onBlur={(e) => (e.currentTarget.style.width = "180px")}
    />
  )
}
