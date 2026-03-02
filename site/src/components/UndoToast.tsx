import { useEffect, useRef } from "react"

interface UndoToastProps {
  visible: boolean
  onUndo: () => void
}

export function UndoToast({ visible, onUndo }: UndoToastProps) {
  const barRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (visible && barRef.current) {
      // Reset then animate
      barRef.current.style.transition = "none"
      barRef.current.style.transform = "scaleX(1)"
      // Trigger reflow
      barRef.current.offsetHeight
      barRef.current.style.transition = "transform 4s linear"
      barRef.current.style.transform = "scaleX(0)"
    }
  }, [visible])

  return (
    <div
      className="fixed bottom-6 left-1/2 flex items-center gap-3 rounded z-[500] whitespace-nowrap"
      style={{
        transform: visible ? "translateX(-50%) translateY(0)" : "translateX(-50%) translateY(2rem)",
        background: "var(--ink)",
        color: "var(--cream)",
        fontFamily: "var(--font-sans)",
        fontSize: "0.85rem",
        padding: "0.6rem 1.2rem",
        opacity: visible ? 1 : 0,
        transition: "opacity 0.2s, transform 0.2s",
        pointerEvents: visible ? "auto" : "none",
      }}
    >
      <span>Article dismissed</span>
      <button
        onClick={onUndo}
        className="cursor-pointer rounded-sm"
        style={{
          background: "none",
          border: "1px solid var(--cream)",
          color: "var(--cream)",
          fontSize: "0.8rem",
          padding: "0.15rem 0.5rem",
          fontFamily: "var(--font-sans)",
        }}
      >
        Undo
      </button>
      <div
        className="absolute bottom-0 left-0 right-0 overflow-hidden"
        style={{ height: "3px", background: "rgba(255,255,255,0.15)", borderRadius: "0 0 4px 4px" }}
      >
        <div
          ref={barRef}
          style={{
            height: "100%",
            background: "var(--cream)",
            width: "100%",
            transformOrigin: "left",
          }}
        />
      </div>
    </div>
  )
}
