"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { toast } from "react-hot-toast";

export default function TrainPage() {
  const params = useParams();
  const router = useRouter();
  const train = params.train as string;

  const API = process.env.NEXT_PUBLIC_HOST!;

  // Train core states
  const [connected, setConnected] = useState(false);
  const [speed, setSpeed] = useState(0);
  const [currentSection, setCurrentSection] = useState("none");
  const [telemetryUrl, setTelemetryUrl] = useState("");
  const [mounted, setMounted] = useState(false);
  
  // Satellite telemetry data states
  const [envData, setEnvData] = useState<any>(null);
  const [motionData, setMotionData] = useState<any>(null);
  const [isCalibrating, setIsCalibrating] = useState(false);
  
  // Stan alarmu
  const [collisionAlarm, setCollisionAlarm] = useState(false);
  const collisionTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [isPending, setIsPending] = useState(false);
  const isPollingPaused = useRef(false);
  const statusRequestRunning = useRef(false);

  const COLLISION_THRESHOLD = 3.0;

  useEffect(() => {
    setMounted(true);
    getStatus();
    
    const interval = setInterval(() => {
      if (!isPollingPaused.current) getStatus();
    }, 1500); 

    return () => clearInterval(interval);
  }, []);

  // Odpytywanie telemetrii
  useEffect(() => {
    if (!telemetryUrl) return;

    const fetchTelemetry = async () => {
      try {
        const controllerEnv = new AbortController();
        const controllerMotion = new AbortController();
        const timeout1 = setTimeout(() => controllerEnv.abort(), 1500);
        const timeout2 = setTimeout(() => controllerMotion.abort(), 1500);

        // Usuwamy ewentualny ukośnik na końcu adresu, żeby uniknąć błędów 404 (np. //api/...)
        const safeUrl = telemetryUrl.endsWith('/') ? telemetryUrl.slice(0, -1) : telemetryUrl;

        const [resEnv, resMotion] = await Promise.all([
          fetch(`${safeUrl}/api/telemetry/env`, { signal: controllerEnv.signal }).catch(() => null),
          fetch(`${safeUrl}/api/telemetry/motion`, { signal: controllerMotion.signal }).catch(() => null)
        ]);

        clearTimeout(timeout1);
        clearTimeout(timeout2);

        if (resEnv && resEnv.ok) setEnvData(await resEnv.json());
        
        if (resMotion && resMotion.ok) {
          const mData = await resMotion.json();
          setMotionData(mData);

          const accelValue = mData?.motion?.total_accel_m_s2;
          
          if (accelValue !== undefined && accelValue > COLLISION_THRESHOLD) {
            if (!collisionAlarm) {
              handleCollision(accelValue);
            }
          }
        }
      } catch (err) {
        // Ciche ignorowanie timeoutów sieciowych
      }
    };

    const telemetryInterval = setInterval(fetchTelemetry, 600);
    return () => clearInterval(telemetryInterval);
  }, [telemetryUrl, collisionAlarm]);

  const getStatus = async () => {
    if (statusRequestRunning.current) return;
    statusRequestRunning.current = true;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 1500);

      const res = await fetch(`${API}/${train}/position`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      const data = await res.json();
      if (!res.ok || data.status === "error") return;

      const d = data.data;
      setConnected(d.connected);
      setSpeed(d.speed);
      setCurrentSection(d.section); 
      
      if (d.telemetry_url && d.telemetry_url !== telemetryUrl) {
        setTelemetryUrl(d.telemetry_url);
      }
    } catch (err: any) {
    } finally {
      statusRequestRunning.current = false;
    }
  };

  const sendCommand = async (endpoint: string, body?: any) => {
    setIsPending(true);
    isPollingPaused.current = true; 
    try {
      const controller = new AbortController();
      // ZWIĘKSZAMY TIMEOUT DO 8 SEKUND (BLE potrzebuje czasu na parowanie!)
      const timeoutId = setTimeout(() => controller.abort(), 8000);

      const res = await fetch(`${API}/${train}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      const data = await res.json();
      if (!res.ok || data.status === "error") throw new Error(data.message || "Request failed");
      
      getStatus(); 
      return data;
    } catch (err: any) {
      throw new Error("Brak odp. serwera (BLE Lag/Timeout)");
    } finally {
      setIsPending(false);
      isPollingPaused.current = false;
    }
  };

  const handleCollision = async (gValue: number) => {
    setCollisionAlarm(true);
    isPollingPaused.current = true; 
    setIsCalibrating(true); 

    toast.error(`KRYTYCZNE ZDERZENIE: Wdrażam hamowanie (${gValue.toFixed(2)} m/s²)!`, {
      duration: 4000,
      id: "collision-toast"
    });

    setTimeout(() => setIsCalibrating(false), 1500);

    if (collisionTimeoutRef.current) clearTimeout(collisionTimeoutRef.current);
    collisionTimeoutRef.current = setTimeout(() => {
        setCollisionAlarm(false);
        isPollingPaused.current = false;
    }, 5000);

    try {
      const controller = new AbortController();
      setTimeout(() => controller.abort(), 1500);

      await fetch(`${API}/${train}/stop`, { method: "POST", signal: controller.signal }).catch(() => {});
      setSpeed(0);

      await fetch(`${API}/${train}/telemetry/reset`, { method: "POST", signal: controller.signal }).catch(() => {});

      await fetch(`${API}/${train}/collision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ g_value: Number(gValue.toFixed(2)) }),
        signal: controller.signal
      }).catch(() => {});

    } catch (e) {
      console.error("Collision handling error:", e);
    }
  };

  const resetSensors = async () => {
    setIsCalibrating(true);
    const id = toast.loading("Kalibracja układu INS...");
    
    setTimeout(() => {
      setIsCalibrating(false);
    }, 1500);

    try {
      const controller = new AbortController();
      setTimeout(() => controller.abort(), 2000);

      const response = await fetch(`${API}/${train}/telemetry/reset`, { 
        method: "POST",
        signal: controller.signal
      });
      
      if (response.ok) {
        toast.success(`System ${train} zresetowany`, { id });
        setCollisionAlarm(false);
      } else {
        throw new Error();
      }
    } catch (error) {
      toast.error("Błąd kalibracji (Serwer zajęty)", { id });
    }
  };

  // DODANO: Obsługa błędów .catch() zabezpiecza przed 'unhandledRejection'
  const connect = () => sendCommand("connect").catch(err => toast.error(err.message));
  const disconnect = () => sendCommand("disconnect").catch(err => toast.error(err.message));
  const stop = () => sendCommand("stop").catch(err => toast.error(err.message));

  const changeSpeed = async (delta: number) => {
    if (isPending || collisionAlarm) return;

    const newSpeed = Math.max(-80, Math.min(80, speed + delta));
    setSpeed(newSpeed);
    try {
      await sendCommand("speed", { speed: newSpeed });
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  if (!mounted) return null;

  const heading = motionData?.compass?.heading_deg ?? null;
  const safeCameraUrl = telemetryUrl.endsWith('/') ? telemetryUrl.slice(0, -1) : telemetryUrl;

  return (
    <div className={`space-y-6 p-4 md:p-6 min-h-screen text-gray-300 max-w-7xl mx-auto transition-colors duration-300 ${collisionAlarm ? 'bg-red-950/20' : ''}`}>
      <button 
        onClick={() => router.push("/")}
        className="text-gray-500 hover:text-white transition-colors flex items-center gap-2"
      >
        <span>←</span> Cofnij
      </button>

      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-gray-800 pb-4 gap-4">
        <h1 className="text-2xl md:text-3xl font-black tracking-widest capitalize flex items-center gap-3 text-blue-500">
          {train} Control Panel
          {connected && <span className="w-3 h-3 rounded-full bg-green-500 animate-pulse"></span>}
        </h1>
        {telemetryUrl && (
          <button
            onClick={resetSensors}
            disabled={isCalibrating}
            className="px-4 py-2 rounded bg-gray-900 border border-gray-700 font-mono text-xs hover:border-blue-500 text-gray-300 transition-all uppercase tracking-wider disabled:opacity-50 disabled:cursor-not-allowed w-full sm:w-auto"
          >
            {isCalibrating ? "Kalibracja..." : "Reset INS"}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* LEFT COLUMN - TELEMETRY SPEED CONTROL */}
        <div className="lg:col-span-5 bg-gray-800 p-4 md:p-6 rounded-2xl shadow border border-gray-700 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-6">
              <p className="text-sm md:text-lg">
                Status:{" "}
                <span className={connected ? "text-green-400 font-bold" : "text-red-400 font-bold"}>
                  {connected ? "Connected" : "Disconnected"}
                </span>
              </p>
              <p className="text-sm md:text-lg font-mono">
                Velocity: <span className="text-yellow-400">{speed}%</span>
              </p>
            </div>

            <div className="bg-gray-900 p-4 rounded-xl mb-6 border border-gray-700 shadow-inner">
              <p className="text-xs text-gray-500 font-bold uppercase tracking-widest mb-1">Current Section</p>
              <p className="text-xl md:text-2xl font-bold text-blue-400">{currentSection}</p>
            </div>

            <div className="flex gap-3 flex-wrap">
              <button 
                onClick={connect} 
                disabled={connected || isPending} 
                className={`flex-1 px-4 py-3 rounded-lg font-bold transition-colors shadow ${(!connected && !isPending) ? 'bg-green-600 text-white hover:bg-green-500' : 'bg-gray-700 text-gray-500 cursor-not-allowed'}`}
              >
                Connect
              </button>

              <button 
                onClick={disconnect} 
                disabled={!connected || isPending} 
                className={`flex-1 px-4 py-3 rounded-lg font-bold transition-colors shadow ${(connected && !isPending) ? 'bg-red-600 text-white hover:bg-red-500' : 'bg-gray-700 text-gray-500 cursor-not-allowed'}`}
              >
                Disconnect
              </button>

              <button 
                onClick={stop} 
                disabled={!connected || isPending} 
                className={`w-full px-4 py-3 mt-3 rounded-lg font-black tracking-widest transition-colors shadow-lg ${(connected && !isPending) ? 'bg-gradient-to-b from-red-600 to-red-800 text-white border-b-4 border-red-950 hover:from-red-500 hover:to-red-700' : 'bg-gray-700 text-gray-500 cursor-not-allowed border-b-4 border-gray-800'}`}
              >
                STOP
              </button>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-gray-700">
            <p className="text-xs text-gray-500 font-bold mb-4 uppercase tracking-widest">Manual Speed Control</p>
            <div className="flex flex-col sm:flex-row gap-4">
              <button
                onClick={() => changeSpeed(10)}
                disabled={!connected || isPending || collisionAlarm}
                className={`flex-1 py-4 rounded-xl font-bold text-sm md:text-lg transition-colors shadow ${(connected && !isPending && !collisionAlarm) ? 'bg-blue-600 text-white hover:bg-blue-500 border-b-4 border-blue-800' : 'bg-gray-700 text-gray-500 cursor-not-allowed border-b-4 border-gray-800'}`}
              >
                SPEED UP (+10)
              </button>

              <button
                onClick={() => changeSpeed(-10)}
                disabled={!connected || isPending || collisionAlarm}
                className={`flex-1 py-4 rounded-xl font-bold text-sm md:text-lg transition-colors shadow ${(connected && !isPending && !collisionAlarm) ? 'bg-blue-600 text-white hover:bg-blue-500 border-b-4 border-blue-800' : 'bg-gray-700 text-gray-500 cursor-not-allowed border-b-4 border-gray-800'}`}
              >
                SPEED DOWN (-10)
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN - LIVE CAMERA HUD + SENSOR MATRIX */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          
          {/* CAMERA COMPONENT */}
          <div className={`bg-gray-800 p-4 rounded-2xl shadow border transition-colors ${collisionAlarm ? 'border-red-600 animate-pulse' : 'border-gray-700'}`}>
            <h3 className="text-gray-500 text-xs font-bold mb-3 uppercase tracking-widest flex items-center justify-between w-full">
              <span className="flex items-center">
                <span className={`w-2 h-2 rounded-full mr-2 ${telemetryUrl ? 'bg-green-500 animate-pulse' : 'bg-gray-600'}`}></span> 
                FPV Live Dashcam
              </span>
              <span className="text-[9px] opacity-40 lowercase font-mono">{telemetryUrl || "Brak URL"}</span>
            </h3>
            <div className="w-full bg-black rounded-xl border border-gray-900 overflow-hidden aspect-video flex items-center justify-center relative shadow-inner">
              {telemetryUrl ? (
                <img 
                  src={`${safeCameraUrl}/video`} 
                  className="w-full h-full object-cover" 
                  alt="Live video feed"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                    e.currentTarget.parentElement!.innerHTML = '<span class="text-gray-600 font-mono text-xs">FPV Stream Unreachable</span>';
                  }}
                />
              ) : (
                <span className="text-gray-600 font-mono text-sm">Camera Disconnected</span>
              )}
              {collisionAlarm && (
                <div className="absolute inset-0 bg-red-600/30 flex items-center justify-center border-4 border-red-600">
                  <span className="bg-black text-red-500 font-black px-4 py-2 rounded-md text-sm md:text-xl tracking-wider border border-red-500 text-center">COLLISION DETECTED</span>
                </div>
              )}
            </div>
          </div>

          {/* TELEMETRY MATRIX BLOCK */}
          <div className="flex flex-col md:grid md:grid-cols-12 gap-6">
            
            {/* INERTIAL NAVIGATION HUD */}
            <div className="md:col-span-8 bg-gray-800/80 p-4 rounded-xl border border-gray-700 shadow backdrop-blur-sm flex flex-col gap-4">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 flex items-center gap-2 border-b border-gray-700 pb-2">
                Inertial Navigation (INS)
              </h2>
              <div className="flex flex-col sm:flex-row gap-4 w-full">
                <div className={`flex-1 p-3 rounded-lg border shadow-inner flex flex-col items-center transition-colors ${collisionAlarm ? 'bg-red-950/40 border-red-700' : 'bg-gray-900 border-gray-700'}`}>
                  <span className="text-[9px] text-gray-500 uppercase">Vibrations</span>
                  <div className={`font-mono text-lg font-bold ${collisionAlarm ? 'text-red-500' : 'text-yellow-400'}`}>
                    {isCalibrating ? '--' : (motionData?.motion?.total_accel_m_s2 !== undefined ? motionData.motion.total_accel_m_s2.toFixed(2) : '--')}
                    <span className="text-[10px] text-gray-500 ml-1">m/s²</span>
                  </div>
                </div>
                <div className="flex-1 bg-gray-900 p-3 rounded-lg border border-gray-700 shadow-inner flex flex-col items-center">
                  <span className="text-[9px] text-gray-500 uppercase">Est. Speed</span>
                  <div className="text-blue-400 font-mono text-lg font-bold">
                    {isCalibrating ? '--' : (motionData?.motion?.total_velocity_km_h !== undefined ? motionData.motion.total_velocity_km_h.toFixed(1) : '--')}
                    <span className="text-[10px] text-gray-500 ml-1">km/h</span>
                  </div>
                </div>
                <div className="flex-1 bg-gray-900 p-3 rounded-lg border border-gray-700 shadow-inner flex flex-col items-center">
                  <span className="text-[9px] text-gray-500 uppercase">Gyro</span>
                  <div className="text-teal-400 font-mono text-lg font-bold">
                    {isCalibrating ? '--' : (motionData?.motion?.total_gyro_rad_s !== undefined ? motionData.motion.total_gyro_rad_s.toFixed(2) : '--')}
                    <span className="text-[10px] text-gray-500 ml-1">rad/s</span>
                  </div>
                </div>
              </div>
            </div>

            {/* DYNAMIC DIGITAL COMPASS ELEMENT */}
            <div className="md:col-span-4 bg-gray-800/80 p-4 rounded-xl border border-gray-700 shadow backdrop-blur-sm flex flex-col items-center justify-center">
              <h2 className="text-[10px] font-bold text-gray-500 uppercase mb-3 self-start w-full border-b border-gray-700 pb-2">Compass</h2>
              <div className="relative w-20 h-20 md:w-24 md:h-24 rounded-full border border-gray-700 bg-black/60 shadow-[inset_0_0_10px_rgba(0,0,0,0.8)] mt-2">
                <div className="absolute inset-0 flex items-center justify-center text-[8px] text-gray-600 font-black">
                  <span className="absolute top-1 text-red-500/80">N</span>
                  <span className="absolute bottom-1">S</span>
                  <span className="absolute left-1">W</span>
                  <span className="absolute right-1">E</span>
                </div>
                <div 
                  className="absolute inset-0 flex items-center justify-center transition-transform duration-300 ease-out"
                  style={{ transform: heading !== null ? `rotate(${heading}deg)` : 'rotate(0deg)' }}
                >
                  <div className="w-0.5 h-10 bg-gradient-to-t from-transparent via-red-500 to-red-500 rounded-full shadow-[0_0_6px_rgba(239,68,68,0.7)]"></div>
                </div>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-1.5 h-1.5 bg-white rounded-full shadow"></div>
                </div>
              </div>
              <div className="mt-3 font-mono text-lg md:text-xl font-bold text-yellow-500">
                {heading !== null ? `${heading}` : '--'}<span className="text-xs text-gray-500">°</span>
              </div>
            </div>

            {/* ATMOSPHERIC SENSORS PANEL */}
            <div className="md:col-span-12 bg-gray-800/80 p-4 rounded-xl border border-gray-700 shadow backdrop-blur-sm flex flex-col gap-3">
              <h2 className="text-[10px] font-bold uppercase tracking-widest text-gray-500 border-b border-gray-700 pb-2 flex items-center gap-2">
                Weather & Air Telemetry
              </h2>
              <div className="flex flex-col sm:flex-row gap-4 w-full">
                <div className="flex-1 border-l-2 border-orange-500/50 pl-3 py-2 bg-gray-900/40 rounded-r-lg">
                  <span className="text-[9px] text-gray-500 uppercase block">Temp</span>
                  <span className="text-lg font-mono font-bold text-orange-400">
                    {envData?.environment?.temperature_c !== undefined ? envData.environment.temperature_c.toFixed(1) : '--'} <span className="text-xs text-gray-600">°C</span>
                  </span>
                </div>
                <div className="flex-1 border-l-2 border-blue-500/50 pl-3 py-2 bg-gray-900/40 rounded-r-lg">
                  <span className="text-[9px] text-gray-500 uppercase block">Humidity</span>
                  <span className="text-lg font-mono font-bold text-blue-400">
                    {envData?.environment?.humidity_percent !== undefined ? envData.environment.humidity_percent.toFixed(1) : '--'} <span className="text-xs text-gray-600">%</span>
                  </span>
                </div>
                <div className="flex-1 border-l-2 border-teal-500/50 pl-3 py-2 bg-gray-900/40 rounded-r-lg">
                  <span className="text-[9px] text-gray-500 uppercase block">Pressure</span>
                  <span className="text-lg font-mono font-bold text-teal-400">
                    {envData?.environment?.pressure_hpa !== undefined ? envData.environment.pressure_hpa.toFixed(0) : '--'} <span className="text-xs text-gray-600">hPa</span>
                  </span>
                </div>
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}
