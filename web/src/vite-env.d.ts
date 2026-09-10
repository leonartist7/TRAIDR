/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TRAIDR_DATA_MODE?: "auto" | "preview";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
