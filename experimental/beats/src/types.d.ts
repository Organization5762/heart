interface ImportMetaEnv {
  readonly VITE_BEATS_APP_VERSION?: string;
  readonly VITE_BEATS_WEBSOCKET_HOST?: string;
  readonly VITE_BEATS_WEBSOCKET_PORT?: string;
  readonly VITE_BEATS_WEBSOCKET_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.proto?raw" {
  const value: string;
  export default value;
}
