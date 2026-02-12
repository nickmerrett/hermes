import { useState, useMemo } from 'react';

const PALETTE = [
  '#3b82f6', '#10b981', '#6366f1', '#ef4444',
  '#f59e0b', '#14b8a6', '#8b5cf6', '#ec4899',
];

function shuffleArray(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function WordCloud({ tags }) {
  const [hoveredTag, setHoveredTag] = useState(null);

  const shuffledTags = useMemo(() => {
    if (!tags || tags.length === 0) return [];
    const maxCount = Math.max(...tags.map(t => t.count));
    const minCount = Math.min(...tags.map(t => t.count));
    const range = maxCount - minCount || 1;

    return shuffleArray(tags.map((t, i) => ({
      ...t,
      fontSize: 12 + ((t.count - minCount) / range) * 24,
      color: PALETTE[i % PALETTE.length],
    })));
  }, [tags]);

  if (!tags || tags.length === 0) {
    return <div className="analytics-empty">No tags available</div>;
  }

  return (
    <div className="word-cloud">
      {shuffledTags.map((t) => (
        <span
          key={t.tag}
          className="word-cloud-tag"
          style={{
            fontSize: `${t.fontSize}px`,
            color: t.color,
          }}
          onMouseEnter={() => setHoveredTag(t.tag)}
          onMouseLeave={() => setHoveredTag(null)}
          title={`${t.tag}: ${t.count}`}
        >
          {t.tag}
          {hoveredTag === t.tag && (
            <span className="word-cloud-tooltip">{t.count}</span>
          )}
        </span>
      ))}
    </div>
  );
}
