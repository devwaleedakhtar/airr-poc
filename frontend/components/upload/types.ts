export type UploadState =
  | { step: "idle" }
  | { step: "uploading" }
  | { step: "uploaded"; workbookId: string; sheets: string[]; selectedSheet: string | null }
  | { step: "converting"; workbookId: string; selectedSheet: string }
  | { step: "extracting"; workbookId: string; selectedSheet: string }
  | { step: "done"; sessionId: string };

