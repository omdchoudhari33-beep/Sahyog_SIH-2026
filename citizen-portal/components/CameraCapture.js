"use client";

import { useEffect, useRef, useState } from "react";
import { useLanguage } from "@/context/LanguageProvider";

// Live in-browser camera: start -> preview -> capture -> retake/use. Falls
// back cleanly to a "denied" state on permission refusal or an unsupported
// browser - the parent (StepEvidence) always keeps the gallery upload
// option available alongside this, so a citizen is never blocked.
export default function CameraCapture({ onCapture }) {
  const { t } = useLanguage();
  const [phase, setPhase] = useState("idle"); // idle | starting | live | captured | denied
  const [capturedUrl, setCapturedUrl] = useState(null);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const canvasRef = useRef(null);

  function stopStream() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  useEffect(() => stopStream, []);

  async function startCamera() {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setPhase("denied");
      return;
    }
    setPhase("starting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setPhase("live");
    } catch {
      setPhase("denied");
    }
  }

  function capture() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        setCapturedUrl(URL.createObjectURL(blob));
        canvas._blob = blob;
      },
      "image/jpeg",
      0.9
    );
    stopStream();
    setPhase("captured");
  }

  function retake() {
    if (capturedUrl) URL.revokeObjectURL(capturedUrl);
    setCapturedUrl(null);
    startCamera();
  }

  function usePhoto() {
    const blob = canvasRef.current?._blob;
    if (!blob) return;
    onCapture(new File([blob], "camera-capture.jpg", { type: "image/jpeg" }));
  }

  return (
    <div>
      <canvas ref={canvasRef} className="hidden" />

      {phase === "idle" && (
        <button type="button" className="gov-btn-secondary" onClick={startCamera}>
          📷 {t("submit.cameraStart")}
        </button>
      )}

      {phase === "starting" && <p className="text-sm text-gray-500">{t("submit.cameraStarting")}</p>}

      {phase === "denied" && <p className="text-sm text-amber-700">{t("submit.cameraDenied")}</p>}

      {phase === "live" && (
        <div>
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <video ref={videoRef} muted playsInline className="w-full max-w-sm rounded-md border border-gov-blue-100" />
          <button type="button" className="gov-btn-primary mt-3" onClick={capture}>
            {t("submit.cameraCapture")}
          </button>
        </div>
      )}

      {phase === "captured" && capturedUrl && (
        <div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={capturedUrl} alt={t("submit.uploadedAlt")} className="w-full max-w-sm rounded-md border border-gov-blue-100" />
          <div className="mt-3 flex gap-3">
            <button type="button" className="gov-btn-secondary" onClick={retake}>
              {t("submit.cameraRetake")}
            </button>
            <button type="button" className="gov-btn-primary" onClick={usePhoto}>
              {t("submit.cameraUsePhoto")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
