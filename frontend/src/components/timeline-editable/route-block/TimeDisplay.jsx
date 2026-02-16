export function TimeDisplay({ start, end }) {
  const formatTime = (time) => {
    if (!time) return '--:--';
    return time.substring(0, 5);
  };

  return (
    <span className="text-[10px] text-white/90 tabular-nums flex-shrink-0 ml-1">
      {formatTime(start)} - {formatTime(end)}
    </span>
  );
}
