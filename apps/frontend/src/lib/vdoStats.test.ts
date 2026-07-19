import { describe, expect, it } from "vitest";
import { isVdoStatsMessage, VdoStatsAccumulator } from "./vdoStats";

describe("VdoStatsAccumulator", () => {
  it("normalizes standard WebRTC counters and derives interval metrics", () => {
    const accumulator = new VdoStatsAccumulator();
    accumulator.read({ stats: [
      { type: "inbound-rtp", kind: "video", bytesReceived: 1_000_000, packetsLost: 10, packetsReceived: 990, jitter: 0.012, framesPerSecond: 30 },
      { type: "candidate-pair", currentRoundTripTime: 0.08, availableOutgoingBitrate: 5_000_000 },
    ] }, 1_000);
    const result = accumulator.read({ stats: [
      { type: "inbound-rtp", kind: "video", bytesReceived: 1_500_000, packetsLost: 12, packetsReceived: 1_488, jitter: 0.014, framesPerSecond: 29.97 },
      { type: "candidate-pair", currentRoundTripTime: 0.09, availableOutgoingBitrate: 4_500_000 },
    ] }, 2_000, { allowOutgoingCapacity: true });

    expect(result?.bitrate_kbps).toBe(4_000);
    expect(result?.available_outgoing_bitrate_kbps).toBe(4_500);
    expect(result?.round_trip_time_ms).toBe(90);
    expect(result?.jitter_ms).toBe(14);
    expect(result?.packet_loss_percent).toBeCloseTo(0.4);
  });

  it("does not mistake the viewer computer upload estimate for phone capacity", () => {
    const result = new VdoStatsAccumulator().read({ stats: [
      { type: "inbound-rtp", kind: "video", bitrateKbps: 1800 },
      { type: "candidate-pair", availableOutgoingBitrate: 50_000_000 },
    ] });
    expect(result?.bitrate_kbps).toBe(1800);
    expect(result?.available_outgoing_bitrate_kbps).toBeUndefined();
  });

  it("ignores overlapping and unchanged counters instead of reporting false zero bitrate", () => {
    const accumulator = new VdoStatsAccumulator();
    accumulator.read({ stats: [
      { type: "inbound-rtp", kind: "video", bytesReceived: 1_000_000 },
    ] }, 1_000);

    const overlapping = accumulator.read({ stats: [
      { type: "inbound-rtp", kind: "video", bytesReceived: 1_100_000 },
    ] }, 1_100);
    const stableCounter = accumulator.read({ stats: [
      { type: "inbound-rtp", kind: "video", bytesReceived: 1_000_000 },
    ] }, 2_000);

    expect(overlapping?.bitrate_kbps).toBeUndefined();
    expect(stableCounter?.bitrate_kbps).toBeUndefined();
  });

  it("accepts compact VDO.Ninja statistics and rejects unrelated events", () => {
    const result = new VdoStatsAccumulator().read({ stats: {
      bitrate_kbps: 2_200,
      packet_loss_percent: 3.5,
      jitter_ms: 18,
      rtt_ms: 120,
    } });
    expect(result).toMatchObject({
      bitrate_kbps: 2_200,
      packet_loss_percent: 3.5,
      jitter_ms: 18,
      round_trip_time_ms: 120,
    });
    expect(isVdoStatsMessage({ action: "view-connection", value: true })).toBe(false);
    expect(isVdoStatsMessage({ cib: "streamml-stats-fresh", stats: {} })).toBe(true);
  });
});
