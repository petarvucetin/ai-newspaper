/* Star rating widget + dismiss — optimistic UI + fetch calls */

document.addEventListener('DOMContentLoaded', () => {
  // --- Dismiss buttons ---
  document.querySelectorAll('.dismiss-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const articleId = btn.dataset.articleId;
      const card = btn.closest('.article-card');
      // Optimistic: collapse card immediately
      card.style.transition = 'opacity 0.2s, transform 0.2s';
      card.style.opacity = '0';
      card.style.transform = 'scale(0.97)';
      setTimeout(() => card.remove(), 200);

      try {
        const resp = await fetch(`/dismiss/${articleId}`, { method: 'DELETE' });
        if (!resp.ok) {
          // Restore on failure
          card.style.opacity = '1';
          card.style.transform = '';
          document.querySelector('.newspaper-grid')?.appendChild(card);
        }
      } catch (err) {
        console.error('Dismiss error:', err);
      }
    });
  });

  // --- Star widgets ---
  document.querySelectorAll('.star-widget').forEach(widget => {
    const articleId = widget.dataset.articleId;
    const stars = widget.querySelectorAll('.star');

    // Hover preview
    stars.forEach((star, idx) => {
      star.addEventListener('mouseenter', () => {
        if (widget.classList.contains('rated')) return;
        stars.forEach((s, i) => {
          s.style.color = i <= idx ? 'var(--star-on)' : 'var(--star-off)';
        });
      });

      star.addEventListener('mouseleave', () => {
        if (widget.classList.contains('rated')) return;
        // Restore to current filled state
        stars.forEach(s => {
          s.style.color = '';
        });
      });

      star.addEventListener('click', async () => {
        if (widget.classList.contains('rated')) return;
        const score = parseInt(star.dataset.value, 10);

        // Optimistic UI: fill stars up to clicked
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
