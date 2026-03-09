import { useState, useCallback } from "react"
import { rateArticle } from "@/api/client"

interface StarRatingProps {
  articleId: number
  userRating: number | null
}

export function StarRating({ articleId, userRating }: StarRatingProps) {
  const [rated, setRated] = useState(userRating !== null && userRating > 0)
  const [score, setScore] = useState(userRating || 0)
  const [hover, setHover] = useState(0)

  const handleClick = useCallback(async (value: number) => {
    if (rated) return
    setScore(value)
    setRated(true)
    try {
      await rateArticle(articleId, value)
    } catch {
      setRated(false)
      setScore(0)
    }
  }, [articleId, rated])

  return (
    <div
      className="flex gap-[2px]"
      style={{
        cursor: rated ? "default" : "pointer",
        opacity: rated ? 0.7 : 1,
        pointerEvents: rated ? "none" : "auto",
      }}
    >
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className="select-none leading-none"
          style={{
            fontSize: "1.1rem",
            color: (hover > 0 ? i <= hover : i <= score) ? "var(--star-on)" : "var(--star-off)",
            transition: "color 0.1s, transform 0.1s",
          }}
          title={`${i} star${i > 1 ? "s" : ""}`}
          onMouseEnter={() => !rated && setHover(i)}
          onMouseLeave={() => !rated && setHover(0)}
          onClick={() => handleClick(i)}
        >
          &#9733;
        </span>
      ))}
    </div>
  )
}
