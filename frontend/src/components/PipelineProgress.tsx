import type { IngestionStage } from "../types";

export const PIPELINE_STAGES: Array<{ id: IngestionStage; label: string }> = [
  { id: "uploaded", label: "Uploaded" },
  { id: "extracting", label: "Extracting text" },
  { id: "chunking", label: "Chunking" },
  { id: "embedding", label: "Generating embeddings" },
  { id: "indexing", label: "Indexing" },
  { id: "completed", label: "Completed" },
];

const ORDER: IngestionStage[] = [
  "uploaded",
  "extracting",
  "chunking",
  "embedding",
  "indexing",
  "completed",
];

type Props = {
  stage: IngestionStage;
};

export function PipelineProgress({ stage }: Props) {
  if (stage === "failed") {
    return (
      <div className="pipeline-progress failed" aria-label="Ingestion failed">
        {PIPELINE_STAGES.map((item) => (
          <div key={item.id} className="pipeline-step failed-step">
            <span className="pipeline-dot" />
            <span>{item.label}</span>
          </div>
        ))}
        <p className="error">Ingestion failed</p>
      </div>
    );
  }

  const currentIndex = ORDER.indexOf(stage);

  return (
    <ol className="pipeline-progress" aria-label="Ingestion pipeline progress">
      {PIPELINE_STAGES.map((item, index) => {
        const state =
          index < currentIndex ? "done" : index === currentIndex ? "current" : "todo";
        return (
          <li key={item.id} className={`pipeline-step ${state}`}>
            <span className="pipeline-dot" aria-hidden="true" />
            <span>{item.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
