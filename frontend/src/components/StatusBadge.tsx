import type { IngestionStage, ProcessingStatus } from "../types";

export type BadgeTone = "ok" | "warn" | "danger";

const STATUS_LABELS: Record<ProcessingStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
};

const STAGE_LABELS: Record<IngestionStage, string> = {
  uploaded: "Uploaded",
  extracting: "Extracting",
  chunking: "Chunking",
  embedding: "Embedding",
  indexing: "Indexing",
  completed: "Completed",
  failed: "Failed",
};

type ToneBadgeProps = {
  tone: BadgeTone;
  children: string;
};

export function ToneBadge({ tone, children }: ToneBadgeProps) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

type StatusBadgeProps = {
  status: ProcessingStatus;
  stage?: IngestionStage;
};

export function StatusBadge({ status, stage }: StatusBadgeProps) {
  const tone: BadgeTone =
    status === "completed" ? "ok" : status === "failed" ? "danger" : "warn";
  const label =
    status === "processing" && stage && stage !== "completed" && stage !== "failed"
      ? STAGE_LABELS[stage]
      : STATUS_LABELS[status];
  return <ToneBadge tone={tone}>{label}</ToneBadge>;
}

export function jobStatusTone(status: string): BadgeTone {
  if (status === "completed" || status === "ok" || status === "ready") return "ok";
  if (status === "failed" || status === "unavailable" || status === "not_ready") return "danger";
  return "warn";
}

type JobStatusBadgeProps = {
  status: string;
};

export function JobStatusBadge({ status }: JobStatusBadgeProps) {
  return <ToneBadge tone={jobStatusTone(status)}>{status}</ToneBadge>;
}
