/* Star rating widget — optimistic UI + fetch calls
   Dismiss logic lives in newspaper.html to support undo. */

document.addEventListener('DOMContentLoaded', () => {
  // --- Star widgets ---
  document.querySelectorAll('.star-widget').forEach(widget => {
    const articleId = widget.dataset.articleId;
    const stars = widget.querySelectorAll('.star');

    // Hover preview (only when not yet rated)
    stars.forEach((star, idx) => {
      star.addEventListener('mouseenter', () => {
        if (widget.classList.contains('rated')) return;
        stars.forEach((s, i) => {
          s.style.color = i <= idx ? 'var(--star-on)' : 'var(--star-off)';
        });
      });

      star.addEventListener('mouseleave', () => {
        if (widget.classList.contains('rated')) return;
        stars.forEach(s => { s.style.color = ''; });
      });

      star.addEventListener('click', async () => {
        if (widget.classList.contains('rated')) return;
        const score = parseInt(star.dataset.value, 10);

        // Optimistic UI: fill stars up to clicked, lock widget
        stars.forEach((s, i) => {
          s.classList.toggle('filled', i < score);
          s.style.color = '';
        });
        widget.classList.add('rated');

        try {
          const resp = await fetch(`/rate/${articleId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ score }),
          });
          if (!resp.ok) {
            console.error('Rating failed:', resp.status);
            widget.classList.remove('rated');
          }
        } catch (err) {
          console.error('Rating error:', err);
          widget.classList.remove('rated');
        }
      });
    });
  });
});
