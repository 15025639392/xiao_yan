const AVATAR_WINDOW_LABEL = "avatar";
const AVATAR_WINDOW_WIDTH = 320;
const AVATAR_WINDOW_HEIGHT = 420;
const AVATAR_WINDOW_MARGIN = 24;

export async function setAvatarWindowVisible(visible: boolean): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }

  if (visible) {
    await showAvatarWindow();
    return;
  }

  await closeAvatarWindow();
}

async function showAvatarWindow(): Promise<void> {
  const [{ WebviewWindow }, windowApi] = await Promise.all([
    import("@tauri-apps/api/webviewWindow"),
    import("@tauri-apps/api/window"),
  ]);

  const existing = await WebviewWindow.getByLabel(AVATAR_WINDOW_LABEL);
  if (existing) {
    await positionAvatarWindow(existing, windowApi);
    await existing.setAlwaysOnTop(true);
    await existing.show();
    return;
  }

  const avatarWindow = new WebviewWindow(AVATAR_WINDOW_LABEL, {
    url: buildAvatarWindowUrl(),
    title: "小晏外显",
    width: AVATAR_WINDOW_WIDTH,
    height: AVATAR_WINDOW_HEIGHT,
    minWidth: AVATAR_WINDOW_WIDTH,
    minHeight: AVATAR_WINDOW_HEIGHT,
    resizable: false,
    decorations: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    visible: false,
    focus: false,
  });

  await waitForAvatarWindowCreated(avatarWindow);
  await positionAvatarWindow(avatarWindow, windowApi);
  await avatarWindow.show();
}

async function closeAvatarWindow(): Promise<void> {
  const { WebviewWindow } = await import("@tauri-apps/api/webviewWindow");
  const avatarWindow = await WebviewWindow.getByLabel(AVATAR_WINDOW_LABEL);
  if (avatarWindow) {
    await avatarWindow.close();
  }
}

type WindowApi = typeof import("@tauri-apps/api/window");
type AvatarWindowHandle = Awaited<ReturnType<WindowApi["Window"]["getByLabel"]>>;

async function positionAvatarWindow(avatarWindow: NonNullable<AvatarWindowHandle>, windowApi: WindowApi): Promise<void> {
  const monitor = await windowApi.currentMonitor();
  if (!monitor) return;

  const scaleFactor = monitor.scaleFactor || 1;
  const physicalWidth = Math.round(AVATAR_WINDOW_WIDTH * scaleFactor);
  const physicalHeight = Math.round(AVATAR_WINDOW_HEIGHT * scaleFactor);
  const physicalMargin = Math.round(AVATAR_WINDOW_MARGIN * scaleFactor);
  const x = monitor.workArea.position.x + monitor.workArea.size.width - physicalWidth - physicalMargin;
  const y = monitor.workArea.position.y + monitor.workArea.size.height - physicalHeight - physicalMargin;

  await avatarWindow.setPosition(new windowApi.PhysicalPosition(Math.max(x, 0), Math.max(y, 0)));
}

function waitForAvatarWindowCreated(avatarWindow: { once: <T>(event: string, handler: (event: { payload: T }) => void) => Promise<() => void> }): Promise<void> {
  return new Promise((resolve, reject) => {
    void avatarWindow.once("tauri://created", () => resolve());
    void avatarWindow.once<string>("tauri://error", (event) => reject(new Error(event.payload || "小晏外显窗口创建失败")));
  });
}

function buildAvatarWindowUrl(): string {
  return `${window.location.origin}${window.location.pathname}#/avatar`;
}

function isTauriRuntime(): boolean {
  return Boolean(
    typeof window !== "undefined" &&
      ("__TAURI_INTERNALS__" in window || "__TAURI__" in window),
  );
}
