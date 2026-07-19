import type { VdoNinjaMetrics } from "../types";

type UnknownRecord = Record<string, unknown>;
type NumberCandidate = { key: string; value: number; owner: UnknownRecord; score: number };

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function normalizedKey(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function recordsWithin(value: unknown, depth = 0, output: UnknownRecord[] = []): UnknownRecord[] {
  if (depth > 8 || output.length >= 500) return output;
  if (Array.isArray(value)) {
    value.forEach((item) => recordsWithin(item, depth + 1, output));
  } else if (isRecord(value)) {
    output.push(value);
    Object.values(value).forEach((item) => recordsWithin(item, depth + 1, output));
  }
  return output;
}

function recordScore(record: UnknownRecord): number {
  const type = String(record.type ?? record.mediaType ?? record.kind ?? "").toLowerCase();
  let score = 0;
  if (type.includes("inbound-rtp")) score += 6;
  if (type.includes("video")) score += 4;
  if (type.includes("candidate-pair")) score += 2;
  if (record.isRemote === true || record.remote === true) score += 1;
  return score;
}

function candidates(value: unknown): NumberCandidate[] {
  const output: NumberCandidate[] = [];
  recordsWithin(value).forEach((owner) => {
    const score = recordScore(owner);
    Object.entries(owner).forEach(([key, raw]) => {
      if (typeof raw === "number" && Number.isFinite(raw) && !Number.isNaN(raw)) {
        output.push({ key: normalizedKey(key), value: raw, owner, score });
      }
    });
  });
  return output;
}

function findNumber(values: NumberCandidate[], aliases: string[]): number | undefined {
  const names = new Set(aliases.map(normalizedKey));
  return values
    .filter((item) => names.has(item.key))
    .sort((left, right) => right.score - left.score)[0]?.value;
}

function finiteRange(value: number | undefined, minimum: number, maximum: number): number | undefined {
  return value != null && Number.isFinite(value) && value >= minimum && value <= maximum
    ? value
    : undefined;
}

function milliseconds(value: number | undefined): number | undefined {
  if (value == null) return undefined;
  return value <= 60 ? value * 1000 : value;
}

function bitrateKbps(value: number | undefined): number | undefined {
  if (value == null) return undefined;
  return value > 100_000 ? value / 1000 : value;
}

export function isVdoStatsMessage(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const action = String(value.action ?? value.type ?? "").toLowerCase();
  const callback = String(value.cib ?? "").toLowerCase();
  return "stats" in value || action.includes("stats") || callback.startsWith("streamml-stats");
}

export class VdoStatsAccumulator {
  private previousBytes?: number;
  private previousPacketsLost?: number;
  private previousPacketsReceived?: number;
  private previousAt?: number;

  read(
    value: unknown,
    observedAtMs = Date.now(),
    options: { allowOutgoingCapacity?: boolean } = {},
  ): VdoNinjaMetrics | null {
    const values = candidates(value);
    if (values.length === 0) return null;

    const bytesReceived = findNumber(values, ["bytesReceived", "videoBytesReceived"]);
    const packetsLost = findNumber(values, ["packetsLost", "videoPacketsLost"]);
    const packetsReceived = findNumber(values, ["packetsReceived", "videoPacketsReceived"]);
    let measuredBitrate = bitrateKbps(findNumber(values, [
      "bitrateKbps", "videoBitrateKbps", "receiveBitrateKbps", "inboundBitrateKbps",
      "bitrate", "videoBitrate", "receiveBitrate",
    ]));
    const elapsedMs = this.previousAt == null ? null : observedAtMs - this.previousAt;
    if (
      measuredBitrate == null && bytesReceived != null && this.previousBytes != null
      && elapsedMs != null && elapsedMs >= 500 && bytesReceived >= this.previousBytes
    ) {
      const byteDelta = bytesReceived - this.previousBytes;
      // An unchanged counter in an otherwise valid stats response does not
      // prove that the mobile uplink has zero capacity. Signal availability is
      // handled by the freshness watchdog instead.
      if (byteDelta > 0) measuredBitrate = byteDelta * 8 / elapsedMs;
    }

    let lossPercent = findNumber(values, ["packetLossPercent", "packetsLostPercent", "lossPercent"]);
    if (lossPercent == null && packetsLost != null && packetsReceived != null) {
      const lost = this.previousPacketsLost != null && packetsLost >= this.previousPacketsLost
        ? packetsLost - this.previousPacketsLost : packetsLost;
      const received = this.previousPacketsReceived != null && packetsReceived >= this.previousPacketsReceived
        ? packetsReceived - this.previousPacketsReceived : packetsReceived;
      if (lost + received > 0) lossPercent = lost * 100 / (lost + received);
    }

    if (bytesReceived != null && (this.previousAt == null || elapsedMs == null || elapsedMs >= 500)) {
      this.previousBytes = bytesReceived;
    }
    if (packetsLost != null) this.previousPacketsLost = packetsLost;
    if (packetsReceived != null) this.previousPacketsReceived = packetsReceived;
    if (this.previousAt == null || elapsedMs == null || elapsedMs >= 500) this.previousAt = observedAtMs;

    const result: VdoNinjaMetrics = {
      bitrate_kbps: finiteRange(measuredBitrate, Number.EPSILON, 100_000),
      available_outgoing_bitrate_kbps: options.allowOutgoingCapacity
        ? finiteRange(bitrateKbps(findNumber(values, [
            "availableOutgoingBitrate", "availableOutgoingBitrateBps", "availableBitrate",
            "bandwidthEstimate", "estimatedAvailableBitrate",
          ])), 0, 100_000)
        : undefined,
      packet_loss_percent: finiteRange(lossPercent, 0, 100),
      packets_lost: finiteRange(packetsLost, 0, Number.MAX_SAFE_INTEGER),
      packets_received: finiteRange(packetsReceived, 0, Number.MAX_SAFE_INTEGER),
      jitter_ms: finiteRange(
        findNumber(values, ["jitterMs"]) ?? milliseconds(findNumber(values, ["jitter", "videoJitter"])),
        0,
        60_000,
      ),
      round_trip_time_ms: finiteRange(
        findNumber(values, ["rttMs", "roundTripTimeMs"])
          ?? milliseconds(findNumber(values, ["currentRoundTripTime", "roundTripTime", "rtt"])),
        0,
        60_000,
      ),
      frames_per_second: finiteRange(findNumber(values, ["framesPerSecond", "fps", "frameRate"]), 0, 240),
      frames_dropped: finiteRange(findNumber(values, ["framesDropped", "droppedFrames"]), 0, Number.MAX_SAFE_INTEGER),
      frames_received: finiteRange(findNumber(values, ["framesReceived", "videoFramesReceived"]), 0, Number.MAX_SAFE_INTEGER),
      frame_width: finiteRange(findNumber(values, ["frameWidth", "videoWidth", "width"]), 0, 16_384),
      frame_height: finiteRange(findNumber(values, ["frameHeight", "videoHeight", "height"]), 0, 16_384),
    };
    const cleaned = Object.fromEntries(Object.entries(result).filter(([, item]) => item != null));
    return Object.keys(cleaned).length > 0 ? cleaned : null;
  }
}
