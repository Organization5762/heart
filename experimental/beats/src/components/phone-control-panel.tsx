import { useWS } from "@/actions/ws/websocket";
import { getConfiguredBeatsWebSocketUrl } from "@/config/websocket";
import { cn } from "@/utils/tailwind";
import {
  Camera,
  ChevronLeft,
  ChevronRight,
  CornerDownLeft,
  Send,
  Smartphone,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

const SESSION_LABEL_FALLBACK = "Heart Totem";
const TEXT_CHARACTER_LIMIT = 500;
const PHOTO_OUTPUT_SIZE = 640;
const PHOTO_JPEG_QUALITY = 0.82;
const PHOTO_MIN_ZOOM = 1;
const PHOTO_MAX_ZOOM = 3;
const PHOTO_ZOOM_STEP = 0.01;
const PHOTO_CROP_BOX_SIZE_PERCENT = 76;
const PHOTO_CROP_BOX_INSET_PERCENT = (100 - PHOTO_CROP_BOX_SIZE_PERCENT) / 2;

type PhoneControlCommand = "browse" | "activate" | "alternate_activate";
type FloatingEmojiKey =
  | "poop"
  | "skull"
  | "heart"
  | "star"
  | "rainbow"
  | "seb"
  | "faye"
  | "will"
  | "clem"
  | "cal"
  | "sri"
  | "lampe"
  | "ditto";
type PhotoDraft = {
  cropOffsetXPercent: number;
  cropOffsetYPercent: number;
  cropZoom: number;
  sourceHeight: number;
  sourceUrl: string;
  sourceWidth: number;
};

type PhoneControlAction = {
  command: PhoneControlCommand;
  description: string;
  icon: ReactNode;
  key: string;
  label: string;
  browseStep?: number;
  tone: "primary" | "secondary";
};

type FloatingEmojiAction = {
  emoji: FloatingEmojiKey;
  glyph: string;
  label: string;
};

const PHONE_CONTROL_ACTIONS: PhoneControlAction[] = [
  {
    key: "previous",
    label: "Previous",
    description: "Browse -1",
    command: "browse",
    browseStep: -1,
    icon: <ChevronLeft className="h-6 w-6" />,
    tone: "secondary",
  },
  {
    key: "next",
    label: "Next",
    description: "Browse +1",
    command: "browse",
    browseStep: 1,
    icon: <ChevronRight className="h-6 w-6" />,
    tone: "secondary",
  },
  {
    key: "activate",
    label: "Activate",
    description: "Primary selection",
    command: "activate",
    icon: <Send className="h-6 w-6" />,
    tone: "primary",
  },
  {
    key: "alternate",
    label: "Alternate",
    description: "Secondary action",
    command: "alternate_activate",
    icon: <CornerDownLeft className="h-6 w-6" />,
    tone: "primary",
  },
];

const FLOATING_EMOJI_ACTIONS: FloatingEmojiAction[] = [
  { emoji: "poop", glyph: "💩", label: "Poop" },
  { emoji: "skull", glyph: "💀", label: "Skull" },
  { emoji: "heart", glyph: "❤️", label: "Heart" },
  { emoji: "star", glyph: "⭐", label: "Star" },
  { emoji: "rainbow", glyph: "🌈", label: "Rainbow" },
];

const FLOATING_FACE_ACTIONS: FloatingEmojiAction[] = [
  { emoji: "seb", glyph: "SE", label: "Seb" },
  { emoji: "faye", glyph: "FA", label: "Faye" },
  { emoji: "will", glyph: "WI", label: "Will" },
  { emoji: "clem", glyph: "CL", label: "Clem" },
  { emoji: "cal", glyph: "CA", label: "Cal" },
  { emoji: "sri", glyph: "SR", label: "Sri" },
  { emoji: "lampe", glyph: "LA", label: "Lampe" },
  { emoji: "ditto", glyph: "DI", label: "Ditto" },
];

export function PhoneControlPanel() {
  const {
    readyState,
    sendEmojiControl,
    sendImageControl,
    sendNavigationControl,
    sendTextControl,
    socket,
  } = useWS();
  const configuredWebsocketUrl = getConfiguredBeatsWebSocketUrl();
  const websocketUrl = socket?.url ?? configuredWebsocketUrl;
  const [lastActionLabel, setLastActionLabel] = useState<string | null>(null);
  const [textDraft, setTextDraft] = useState("");
  const [photoDraft, setPhotoDraft] = useState<PhotoDraft | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [isPreparingPhoto, setIsPreparingPhoto] = useState(false);
  const [isSendingPhoto, setIsSendingPhoto] = useState(false);
  const [isDraggingPhoto, setIsDraggingPhoto] = useState(false);
  const photoInputRef = useRef<HTMLInputElement | null>(null);
  const cropFrameRef = useRef<HTMLDivElement | null>(null);
  const activeCropPointersRef = useRef<Map<number, { x: number; y: number }>>(
    new Map(),
  );
  const activeCropDragRef = useRef<{
    pointerId: number;
    startClientX: number;
    startClientY: number;
    startOffsetXPercent: number;
    startOffsetYPercent: number;
  } | null>(null);
  const activePinchRef = useRef<{
    startDistance: number;
    startZoom: number;
  } | null>(null);
  const isConnected = readyState === WebSocket.OPEN;
  const controlsLocked = !isConnected;
  const trimmedTextDraft = textDraft.trim();
  const canSendText = isConnected && trimmedTextDraft.length > 0;
  const canSendPhoto =
    isConnected && photoDraft !== null && !isPreparingPhoto && !isSendingPhoto;
  const sessionLabel = useMemo(
    () => getPhoneSessionLabel(websocketUrl),
    [websocketUrl],
  );
  const photoPreviewMetrics = useMemo(
    () => (photoDraft ? getPhotoPreviewMetrics(photoDraft) : null),
    [photoDraft],
  );
  const photoSourceUrl = photoDraft?.sourceUrl ?? null;

  useEffect(() => {
    return () => {
      if (photoSourceUrl) {
        URL.revokeObjectURL(photoSourceUrl);
      }
    };
  }, [photoSourceUrl]);

  const handleAction = (action: PhoneControlAction) => {
    if (controlsLocked) {
      return;
    }

    const sent = sendNavigationControl(action.command, action.browseStep);
    if (!sent) {
      return;
    }

    setLastActionLabel(action.label);
  };

  const handleTextSubmit = () => {
    if (!canSendText) {
      return;
    }

    const sent = sendTextControl(trimmedTextDraft);
    if (!sent) {
      return;
    }

    setLastActionLabel(`Text: ${summarizeText(trimmedTextDraft)}`);
  };

  const handleTextClear = () => {
    if (!isConnected) {
      return;
    }

    const sent = sendTextControl(null);
    if (!sent) {
      return;
    }

    setTextDraft("");
    setLastActionLabel("Text cleared");
  };

  const handleEmojiSend = (action: FloatingEmojiAction) => {
    if (controlsLocked) {
      return;
    }

    const sent = sendEmojiControl(action.emoji);
    if (!sent) {
      return;
    }

    setLastActionLabel(`${action.label} emoji`);
  };

  const handleStartPhotoCapture = () => {
    if (isPreparingPhoto) {
      return;
    }
    photoInputRef.current?.click();
  };

  const handlePhotoSelection = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }

    setIsPreparingPhoto(true);
    setPhotoError(null);

    try {
      const draft = await preparePhotoDraft(file);
      setPhotoDraft(draft);
      setLastActionLabel(
        `Photo ready: ${draft.sourceWidth}x${draft.sourceHeight}`,
      );
    } catch (error) {
      console.error("Failed to prepare photo draft", error);
      setPhotoError("Could not prepare that image. Try another photo.");
    } finally {
      setIsPreparingPhoto(false);
    }
  };

  const handlePhotoClear = () => {
    setPhotoDraft(null);
    setPhotoError(null);
    setIsDraggingPhoto(false);
    activeCropPointersRef.current.clear();
    activeCropDragRef.current = null;
    activePinchRef.current = null;
  };

  const handlePhotoSend = async () => {
    if (!canSendPhoto || photoDraft === null) {
      return;
    }

    setIsSendingPhoto(true);
    setPhotoError(null);
    try {
      const payload = await renderPhotoCrop(photoDraft);
      const sent = sendImageControl(payload.base64, payload.mimeType);
      if (!sent) {
        setPhotoError("Socket offline. Reconnect before sending the photo.");
        return;
      }

      setLastActionLabel(
        `Photo sent: ${photoDraft.sourceWidth}x${photoDraft.sourceHeight} -> ${PHOTO_OUTPUT_SIZE}x${PHOTO_OUTPUT_SIZE}`,
      );
    } catch (error) {
      console.error("Failed to export cropped photo", error);
      setPhotoError("Could not export that crop. Try retaking the photo.");
    } finally {
      setIsSendingPhoto(false);
    }
  };

  const handlePhotoZoomChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const nextZoom = Number(event.target.value);
    setPhotoDraft((current) =>
      current
        ? normalizePhotoDraft({ ...current, cropZoom: nextZoom })
        : current,
    );
  };

  const handlePhotoPointerDown = (
    event: React.PointerEvent<HTMLDivElement>,
  ) => {
    if (!photoDraft) {
      return;
    }
    event.preventDefault();
    activeCropPointersRef.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });
    if (activeCropPointersRef.current.size === 1) {
      activeCropDragRef.current = {
        pointerId: event.pointerId,
        startClientX: event.clientX,
        startClientY: event.clientY,
        startOffsetXPercent: photoDraft.cropOffsetXPercent,
        startOffsetYPercent: photoDraft.cropOffsetYPercent,
      };
      activePinchRef.current = null;
      setIsDraggingPhoto(true);
    } else if (activeCropPointersRef.current.size === 2) {
      const [firstPointer, secondPointer] = Array.from(
        activeCropPointersRef.current.values(),
      );
      activeCropDragRef.current = null;
      activePinchRef.current = {
        startDistance: distanceBetweenPoints(firstPointer, secondPointer),
        startZoom: photoDraft.cropZoom,
      };
      setIsDraggingPhoto(false);
    }
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePhotoPointerMove = (
    event: React.PointerEvent<HTMLDivElement>,
  ) => {
    const frameSize = cropFrameRef.current?.clientWidth ?? 0;
    if (!photoDraft || frameSize <= 0) {
      return;
    }
    activeCropPointersRef.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    });

    const activePinch = activePinchRef.current;
    if (activePinch && activeCropPointersRef.current.size >= 2) {
      const [firstPointer, secondPointer] = Array.from(
        activeCropPointersRef.current.values(),
      );
      const nextDistance = distanceBetweenPoints(firstPointer, secondPointer);
      if (activePinch.startDistance > 0 && Number.isFinite(nextDistance)) {
        const nextZoom =
          activePinch.startZoom * (nextDistance / activePinch.startDistance);
        setPhotoDraft((current) =>
          current
            ? normalizePhotoDraft({
                ...current,
                cropZoom: nextZoom,
              })
            : current,
        );
      }
      return;
    }

    const activeDrag = activeCropDragRef.current;
    if (!activeDrag || activeDrag.pointerId !== event.pointerId) {
      return;
    }

    const deltaXPercent =
      ((event.clientX - activeDrag.startClientX) / frameSize) * 100;
    const deltaYPercent =
      ((event.clientY - activeDrag.startClientY) / frameSize) * 100;
    setPhotoDraft((current) =>
      current
        ? normalizePhotoDraft({
            ...current,
            cropOffsetXPercent: activeDrag.startOffsetXPercent + deltaXPercent,
            cropOffsetYPercent: activeDrag.startOffsetYPercent + deltaYPercent,
          })
        : current,
    );
  };

  const stopPhotoDragging = () => {
    activeCropPointersRef.current.clear();
    activeCropDragRef.current = null;
    activePinchRef.current = null;
    setIsDraggingPhoto(false);
  };

  const handlePhotoPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    activeCropPointersRef.current.delete(event.pointerId);
    if (activeCropDragRef.current?.pointerId === event.pointerId) {
      activeCropDragRef.current = null;
      setIsDraggingPhoto(false);
    }
    if (activePinchRef.current && activeCropPointersRef.current.size < 2) {
      activePinchRef.current = null;
    }
  };

  return (
    <section className="flex min-h-svh w-full flex-col gap-4 sm:py-6">
      <div className="beats-console-panel flex min-h-svh flex-1 flex-col rounded-none px-3 py-5 sm:min-h-0 sm:rounded-[1.75rem] sm:px-6 sm:py-6">
        <input
          ref={photoInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={handlePhotoSelection}
        />
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="beats-console-kicker font-tomorrow text-[11px] tracking-[0.22em] uppercase">
              Offline Phone Prototype
            </p>
            <h1 className="font-tomorrow mt-2 text-3xl tracking-[0.08em] text-slate-100 uppercase">
              Totem Control
            </h1>
            <p className="beats-console-copy mt-3 text-sm leading-6">
              A minimal browser surface for browsing and activating the totem
              over the existing websocket contract.
            </p>
          </div>
          <div className="beats-console-card rounded-2xl p-3 text-slate-100">
            <Smartphone className="h-6 w-6" />
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:mt-5 sm:grid-cols-2">
          <StatusCard
            label="Session"
            value={sessionLabel}
            helper="Use this label in the QR flow so people know they joined the right totem."
          />
          <StatusCard
            label="Socket"
            value={formatSocketStateLabel(readyState)}
            helper={
              isConnected
                ? "Runtime websocket is ready for public controls."
                : "Reconnect the websocket before exposing this to attendees."
            }
            highlight={isConnected}
          />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:mt-5">
          {PHONE_CONTROL_ACTIONS.map((action) => (
            <button
              key={action.key}
              type="button"
              disabled={controlsLocked}
              onClick={() => handleAction(action)}
              className={cn(
                "flex min-h-36 flex-col items-start justify-between rounded-[1.4rem] border px-4 py-4 text-left transition active:translate-y-[1px] disabled:cursor-not-allowed disabled:opacity-45",
                action.tone === "primary"
                  ? "border-emerald-300/30 bg-emerald-400/12 text-emerald-50 hover:bg-emerald-400/18"
                  : "border-sky-300/28 bg-sky-400/10 text-sky-50 hover:bg-sky-400/16",
              )}
              aria-label={`${action.label} ${action.description}`}
            >
              <div className="rounded-full border border-white/12 bg-black/20 p-3">
                {action.icon}
              </div>
              <div>
                <div className="font-tomorrow text-base tracking-[0.12em] uppercase">
                  {action.label}
                </div>
                <div className="mt-2 text-sm leading-5 text-current/80">
                  {action.description}
                </div>
              </div>
            </button>
          ))}
        </div>

        <div className="mt-4 grid gap-3 sm:mt-5">
          <div className="beats-console-card rounded-2xl px-4 py-4">
            <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
              Floating Emoji
            </div>
            <div className="mt-3 grid grid-cols-5 gap-2">
              {FLOATING_EMOJI_ACTIONS.map((action) => (
                <button
                  key={action.emoji}
                  type="button"
                  disabled={controlsLocked}
                  onClick={() => handleEmojiSend(action)}
                  className="flex aspect-square min-h-16 items-center justify-center rounded-[1.1rem] border border-fuchsia-300/25 bg-fuchsia-400/10 text-3xl transition hover:bg-fuchsia-400/16 active:translate-y-[1px] disabled:cursor-not-allowed disabled:opacity-45"
                  aria-label={`Send ${action.label} emoji`}
                >
                  <span aria-hidden="true">{action.glyph}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="beats-console-card rounded-2xl px-4 py-4">
            <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
              Floating Faces
            </div>
            <div className="mt-3 grid grid-cols-4 gap-2">
              {FLOATING_FACE_ACTIONS.map((action) => (
                <button
                  key={action.emoji}
                  type="button"
                  disabled={controlsLocked}
                  onClick={() => handleEmojiSend(action)}
                  className="font-tomorrow flex aspect-square min-h-14 items-center justify-center rounded-[1.1rem] border border-amber-300/25 bg-amber-400/10 text-sm tracking-[0.1em] text-amber-50 transition hover:bg-amber-400/16 active:translate-y-[1px] disabled:cursor-not-allowed disabled:opacity-45"
                  aria-label={`Send ${action.label} face`}
                >
                  <span aria-hidden="true">{action.glyph}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="beats-console-card rounded-2xl px-4 py-4">
            <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
              Display Text
            </div>
            <div className="mt-2 text-sm leading-6 text-[#95a2b6]">
              Send free text to the totem over Wi-Fi using the existing Beats
              socket.
            </div>
            <label className="mt-3 block">
              <span className="sr-only">Text to display on the totem</span>
              <textarea
                value={textDraft}
                maxLength={TEXT_CHARACTER_LIMIT}
                disabled={!isConnected}
                onChange={(event) => setTextDraft(event.target.value)}
                placeholder="Type the message to show on the totem"
                rows={4}
                className="min-h-28 w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-base leading-6 text-slate-100 transition outline-none placeholder:text-slate-400/70 focus:border-emerald-300/40 focus:ring-2 focus:ring-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-45"
              />
            </label>
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-[#95a2b6]">
              <span>
                {textDraft.length}/{TEXT_CHARACTER_LIMIT} characters
              </span>
              <span>
                {trimmedTextDraft
                  ? "Ready to send"
                  : "Enter text to enable send"}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <button
                type="button"
                disabled={!canSendText}
                onClick={handleTextSubmit}
                className="font-tomorrow flex min-h-14 items-center justify-center gap-2 rounded-[1.1rem] border border-emerald-300/30 bg-emerald-400/12 px-4 py-3 text-sm tracking-[0.12em] text-emerald-50 uppercase transition hover:bg-emerald-400/18 active:translate-y-[1px] disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Send className="h-4 w-4" />
                Send
              </button>
              <button
                type="button"
                disabled={!isConnected}
                onClick={handleTextClear}
                className="font-tomorrow flex min-h-14 items-center justify-center gap-2 rounded-[1.1rem] border border-white/12 bg-white/5 px-4 py-3 text-sm tracking-[0.12em] text-slate-100 uppercase transition hover:bg-white/10 active:translate-y-[1px] disabled:cursor-not-allowed disabled:opacity-45"
              >
                <X className="h-4 w-4" />
                Clear
              </button>
            </div>
          </div>
          <div className="beats-console-card rounded-2xl px-4 py-4">
            <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
              Display Photo
            </div>
            <div className="mt-2 text-sm leading-6 text-[#95a2b6]">
              Open the camera on your phone, preview the shot, then push it to
              the totem using the same full-screen fitted image path as
              `photo_only`.
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <button
                type="button"
                disabled={isPreparingPhoto}
                onClick={handleStartPhotoCapture}
                className="font-tomorrow flex min-h-14 items-center justify-center gap-2 rounded-[1.1rem] border border-sky-300/28 bg-sky-400/10 px-4 py-3 text-sm tracking-[0.12em] text-sky-50 uppercase transition hover:bg-sky-400/16 active:translate-y-[1px] disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Camera className="h-4 w-4" />
                {photoDraft ? "Retake" : "Take Photo"}
              </button>
              <button
                type="button"
                disabled={!canSendPhoto}
                onClick={handlePhotoSend}
                className="font-tomorrow flex min-h-14 items-center justify-center gap-2 rounded-[1.1rem] border border-emerald-300/30 bg-emerald-400/12 px-4 py-3 text-sm tracking-[0.12em] text-emerald-50 uppercase transition hover:bg-emerald-400/18 active:translate-y-[1px] disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Send className="h-4 w-4" />
                Send Photo
              </button>
            </div>
            <div className="mt-2 text-xs text-[#95a2b6]">
              {isPreparingPhoto
                ? "Preparing photo..."
                : photoDraft
                  ? "Move the image behind the square crop box, or pinch to zoom."
                  : "On mobile this button should open the camera directly."}
            </div>
            {photoError ? (
              <div className="mt-2 text-sm text-rose-300">{photoError}</div>
            ) : null}
            {photoDraft ? (
              <div
                ref={cropFrameRef}
                className={cn(
                  "relative mt-3 aspect-square touch-none overflow-hidden rounded-2xl bg-black/30 select-none",
                  isDraggingPhoto ? "cursor-grabbing" : "cursor-grab",
                )}
                onPointerDown={handlePhotoPointerDown}
                onPointerMove={handlePhotoPointerMove}
                onPointerUp={handlePhotoPointerUp}
                onPointerCancel={stopPhotoDragging}
              >
                <img
                  src={photoDraft.sourceUrl}
                  alt="Square crop preview"
                  draggable={false}
                  className="pointer-events-none absolute max-w-none"
                  style={{
                    width: `${photoPreviewMetrics?.renderedWidthPercent ?? 100}%`,
                    height: `${photoPreviewMetrics?.renderedHeightPercent ?? 100}%`,
                    left: `calc(50% + ${photoDraft.cropOffsetXPercent}%)`,
                    top: `calc(50% + ${photoDraft.cropOffsetYPercent}%)`,
                    transform: "translate(-50%, -50%)",
                  }}
                />
                <div
                  className="pointer-events-none absolute rounded-[1.35rem] border-2 border-white/85 shadow-[0_0_0_9999px_rgba(0,0,0,0.42),inset_0_0_0_1px_rgba(0,0,0,0.28)]"
                  style={{
                    inset: `${PHOTO_CROP_BOX_INSET_PERCENT}%`,
                  }}
                />
              </div>
            ) : null}
            {photoDraft ? (
              <label className="mt-3 block">
                <div className="mb-2 flex items-center justify-between gap-3 text-xs text-[#95a2b6]">
                  <span>Zoom</span>
                  <span>{photoDraft.cropZoom.toFixed(2)}x</span>
                </div>
                <input
                  type="range"
                  min={PHOTO_MIN_ZOOM}
                  max={PHOTO_MAX_ZOOM}
                  step={PHOTO_ZOOM_STEP}
                  value={photoDraft.cropZoom}
                  onChange={handlePhotoZoomChange}
                  className="w-full accent-emerald-300"
                />
              </label>
            ) : null}
            {photoDraft ? (
              <div className="mt-2 text-xs text-[#95a2b6]">
                Source {photoDraft.sourceWidth}x{photoDraft.sourceHeight},
                exported as a square {PHOTO_OUTPUT_SIZE}x{PHOTO_OUTPUT_SIZE}{" "}
                crop.
              </div>
            ) : null}
            {photoDraft ? (
              <button
                type="button"
                onClick={handlePhotoClear}
                className="font-tomorrow mt-3 flex min-h-12 w-full items-center justify-center gap-2 rounded-[1.1rem] border border-white/12 bg-white/5 px-4 py-3 text-sm tracking-[0.12em] text-slate-100 uppercase transition hover:bg-white/10 active:translate-y-[1px]"
              >
                <X className="h-4 w-4" />
                Remove Photo
              </button>
            ) : null}
          </div>
          <StatusCard
            label="Last Action"
            value={lastActionLabel ?? "None yet"}
            helper={
              lastActionLabel
                ? "Most recent command sent from this browser session."
                : "Tap a control once the websocket is online."
            }
          />
        </div>
      </div>
    </section>
  );
}

function StatusCard({
  helper,
  highlight = false,
  label,
  value,
}: {
  helper: string;
  highlight?: boolean;
  label: string;
  value: string;
}) {
  return (
    <div className="beats-console-card rounded-2xl px-4 py-3">
      <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
        {label}
      </div>
      <div
        className={cn(
          "mt-2 font-mono text-lg break-words text-slate-100",
          highlight && "text-emerald-300",
        )}
      >
        {value}
      </div>
      <div className="mt-2 text-sm leading-6 text-[#95a2b6]">{helper}</div>
    </div>
  );
}

export function formatSocketStateLabel(readyState: number): string {
  switch (readyState) {
    case WebSocket.CONNECTING:
      return "Connecting";
    case WebSocket.OPEN:
      return "Online";
    case WebSocket.CLOSING:
      return "Closing";
    default:
      return "Offline";
  }
}

export function getPhoneSessionLabel(websocketUrl: string | null): string {
  if (websocketUrl) {
    try {
      return new URL(websocketUrl).host || SESSION_LABEL_FALLBACK;
    } catch {
      return websocketUrl;
    }
  }

  if (typeof window !== "undefined" && window.location.host) {
    return window.location.host;
  }

  return SESSION_LABEL_FALLBACK;
}

function summarizeText(text: string): string {
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= 28) {
    return compact;
  }
  return `${compact.slice(0, 25)}...`;
}

async function preparePhotoDraft(file: File): Promise<PhotoDraft> {
  const sourceUrl = URL.createObjectURL(file);
  try {
    const image = await loadImageElement(sourceUrl);
    return normalizePhotoDraft({
      cropOffsetXPercent: 0,
      cropOffsetYPercent: 0,
      cropZoom: PHOTO_MIN_ZOOM,
      sourceHeight: image.naturalHeight,
      sourceUrl,
      sourceWidth: image.naturalWidth,
    });
  } catch (error) {
    URL.revokeObjectURL(sourceUrl);
    throw error;
  }
}

function getPhotoPreviewMetrics(photoDraft: PhotoDraft): {
  renderedHeightPercent: number;
  renderedWidthPercent: number;
} {
  const coverScale =
    PHOTO_CROP_BOX_SIZE_PERCENT /
    Math.min(photoDraft.sourceWidth, photoDraft.sourceHeight);
  return {
    renderedHeightPercent:
      photoDraft.sourceHeight * coverScale * photoDraft.cropZoom,
    renderedWidthPercent:
      photoDraft.sourceWidth * coverScale * photoDraft.cropZoom,
  };
}

function normalizePhotoDraft(photoDraft: PhotoDraft): PhotoDraft {
  return {
    ...photoDraft,
    cropZoom: clamp(photoDraft.cropZoom, PHOTO_MIN_ZOOM, PHOTO_MAX_ZOOM),
  };
}

async function renderPhotoCrop(photoDraft: PhotoDraft): Promise<{
  base64: string;
  mimeType: string;
}> {
  const image = await loadImageElement(photoDraft.sourceUrl);
  const preview = getPhotoPreviewMetrics(photoDraft);
  const editorSize = Math.round(
    PHOTO_OUTPUT_SIZE / (PHOTO_CROP_BOX_SIZE_PERCENT / 100),
  );
  const editorCanvas = document.createElement("canvas");
  editorCanvas.width = editorSize;
  editorCanvas.height = editorSize;
  const editorContext = editorCanvas.getContext("2d");
  if (editorContext === null) {
    throw new Error("Canvas 2D context unavailable");
  }

  const renderedWidth = (preview.renderedWidthPercent / 100) * editorSize;
  const renderedHeight = (preview.renderedHeightPercent / 100) * editorSize;
  const offsetX =
    (editorSize - renderedWidth) / 2 +
    (photoDraft.cropOffsetXPercent / 100) * editorSize;
  const offsetY =
    (editorSize - renderedHeight) / 2 +
    (photoDraft.cropOffsetYPercent / 100) * editorSize;

  editorContext.imageSmoothingEnabled = true;
  editorContext.imageSmoothingQuality = "high";
  editorContext.drawImage(
    image,
    offsetX,
    offsetY,
    renderedWidth,
    renderedHeight,
  );

  const cropInset = Math.round((editorSize - PHOTO_OUTPUT_SIZE) / 2);
  const outputCanvas = document.createElement("canvas");
  outputCanvas.width = PHOTO_OUTPUT_SIZE;
  outputCanvas.height = PHOTO_OUTPUT_SIZE;
  const outputContext = outputCanvas.getContext("2d");
  if (outputContext === null) {
    throw new Error("Canvas 2D context unavailable");
  }
  outputContext.imageSmoothingEnabled = true;
  outputContext.imageSmoothingQuality = "high";
  outputContext.drawImage(
    editorCanvas,
    cropInset,
    cropInset,
    PHOTO_OUTPUT_SIZE,
    PHOTO_OUTPUT_SIZE,
    0,
    0,
    PHOTO_OUTPUT_SIZE,
    PHOTO_OUTPUT_SIZE,
  );

  const blob = await canvasToBlob(
    outputCanvas,
    "image/jpeg",
    PHOTO_JPEG_QUALITY,
  );
  return {
    base64: await blobToBase64(blob),
    mimeType: blob.type || "image/jpeg",
  };
}

function loadImageElement(sourceUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      resolve(image);
    };
    image.onerror = () => {
      reject(new Error("Image decode failed"));
    };
    image.src = sourceUrl;
  });
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function distanceBetweenPoints(
  firstPoint: { x: number; y: number },
  secondPoint: { x: number; y: number },
): number {
  return Math.hypot(secondPoint.x - firstPoint.x, secondPoint.y - firstPoint.y);
}

function canvasToBlob(
  canvas: HTMLCanvasElement,
  type: string,
  quality: number,
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob === null) {
          reject(new Error("Canvas export failed"));
          return;
        }
        resolve(blob);
      },
      type,
      quality,
    );
  });
}

async function blobToBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";
  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }
  return btoa(binary);
}
