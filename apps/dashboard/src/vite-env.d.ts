/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TARGETS_API_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
