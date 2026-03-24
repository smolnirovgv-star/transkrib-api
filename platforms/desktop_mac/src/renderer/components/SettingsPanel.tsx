import React, { useState, useRef, useEffect } from "react";
import { Settings, Globe, Clock, X, Zap } from "lucide-react";
import { useTranslation, Language } from "../i18n";

interface Props {
  open: boolean;
  onClose: () => void;
}

const DURATION_OPTIONS = [
  { label: "1 min", value: 1 * 60 },
  { label: "3 min", value: 3 * 60 },
  { label: "5 min", value: 5 * 60 },
  { label: "10 min", value: 10 * 60 },
  { label: "15 min", value: 15 * 60 },
  { label: "20 min", value: 20 * 60 },
  { label: "30 min", value: 30 * 60 },
  { label: "No limit", value: 0 },
];

export const DURATION_STORAGE_KEY = "transkrib-video-duration";
export const DEFAULT_DURATION = 15 * 60;

export function getSelectedDuration(): number {
  const saved = localStorage.getItem(DURATION_STORAGE_KEY);
  if (saved !== null) return parseInt(saved, 10);
  return DEFAULT_DURATION;
}

export type WhisperModel = "tiny" | "small" | "medium";

const WHISPER_MODEL_OPTIONS: { label: string; value: WhisperModel; hint: string }[] = [
  { label: "FAST",   value: "tiny",   hint: "tiny"   },
  { label: "MID",    value: "small",  hint: "small"  },
  { label: "SLOW",   value: "medium", hint: "medium" },
];

export const WHISPER_MODEL_KEY = "transkrib-whisper-model";
export const DEFAULT_WHISPER_MODEL: WhisperModel = "tiny";

export function getSelectedModel(): WhisperModel {
  const saved = localStorage.getItem(WHISPER_MODEL_KEY) as WhisperModel | null;
  if (saved && ["tiny", "small", "medium"].includes(saved)) return saved;
  return DEFAULT_WHISPER_MODEL;
}

export const SettingsPanel: React.FC<Props> = ({ open, onClose }) => {
  const { t, language, setLanguage } = useTranslation();
  const [duration, setDuration] = useState<number>(getSelectedDuration);
  const [whisperModel, setWhisperModel] = useState<WhisperModel>(getSelectedModel);
  const drawerRef = useRef<HTMLDivElement>(null);

  const handleDuration = (val: number) => {
    setDuration(val);
    localStorage.setItem(DURATION_STORAGE_KEY, String(val));
  };

  const handleWhisperModel = (val: WhisperModel) => {
    setWhisperModel(val);
    localStorage.setItem(WHISPER_MODEL_KEY, val);
  };

  // Click-outside to close (only when open)
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const timer = setTimeout(() => document.addEventListener("mousedown", handleClick), 50);
    return () => { clearTimeout(timer); document.removeEventListener("mousedown", handleClick); };
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      {open && <div className="settings-backdrop" onClick={onClose} />}
      {/* Drawer */}
      <div ref={drawerRef} className={"settings-drawer" + (open ? " open" : "")}>
        <div className="settings-drawer-header">
          <span className="settings-drawer-title">
            <Settings size={16} /> {t("settings.title")}
          </span>
          <button className="settings-drawer-close btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="settings-drawer-body">
          <div className="settings-group">
            <label className="settings-label"><Globe size={13} /> {t("settings.language")}</label>
            <div className="lang-buttons">
              {(["ru", "en", "zh"] as Language[]).map((l) => (
                <button key={l} className={"btn-lang" + (language === l ? " active" : "")}
                  onClick={() => setLanguage(l)}>
                  {l.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="settings-group">
            <label className="settings-label"><Zap size={13} /> {t("settings.whisperModel")}</label>
            <div className="whisper-model-buttons">
              {WHISPER_MODEL_OPTIONS.map((opt) => (
                <button key={opt.value}
                  className={"btn-whisper-model" + (whisperModel === opt.value ? " active" : "")}
                  onClick={() => handleWhisperModel(opt.value)} title={opt.hint}>
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="settings-group">
            <label className="settings-label"><Clock size={13} /> {t("settings.videoDuration")}</label>
            <div className="duration-buttons">
              {DURATION_OPTIONS.map((opt) => (
                <button key={opt.value}
                  className={"btn-duration" + (duration === opt.value ? " active" : "")}
                  onClick={() => handleDuration(opt.value)}>
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
