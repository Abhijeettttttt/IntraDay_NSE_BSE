import { useEffect, useRef } from "react";
import { createChart } from "lightweight-charts";

// Convert ISO timestamp -> UNIX seconds (lightweight-charts intraday format).
function toTime(iso) {
  return Math.floor(new Date(iso).getTime() / 1000);
}

export default function PriceChart({ candles, overlays }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !candles?.length) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#1e293b" },
        textColor: "#e2e8f0",
      },
      grid: {
        vertLines: { color: "#334155" },
        horzLines: { color: "#334155" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
      autoSize: true,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderVisible: false,
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
    });
    candleSeries.setData(
      candles.map((c) => ({
        time: toTime(c.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // Overlay lines (VWAP, EMAs) sharing the price scale.
    const addLine = (color, key) => {
      if (!overlays?.[key]) return;
      const s = chart.addLineSeries({ color, lineWidth: 1 });
      const data = overlays.time
        .map((t, i) => ({ time: toTime(t), value: overlays[key][i] }))
        .filter((d) => d.value != null);
      s.setData(data);
    };
    addLine("#f59e0b", "vwap");
    addLine("#3b82f6", "ema9");
    addLine("#a855f7", "ema20");

    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [candles, overlays]);

  return <div ref={containerRef} className="chart" />;
}
