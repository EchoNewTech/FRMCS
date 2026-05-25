"use client";

import { useEffect, useState, useRef } from "react";

export default function StationBoard() {
  const API = process.env.NEXT_PUBLIC_HOST!;
  
  const [timeStr, setTimeStr] = useState("00:00:00");
  const [zones, setZones] = useState<Record<string, string | null>>({});
  const [trainsInRoute, setTrainsInRoute] = useState<string[]>(["Express", "Cargo"]);
  
  const previousZonesRef = useRef<Record<string, string | null>>({});
  const audioContextRef = useRef<AudioContext | null>(null);

  // 1. Live Real-Time Clock
  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString("pl-PL", { hour12: false }));
    };
    updateClock();
    const clockInterval = setInterval(updateClock, 1000);
    return () => clearInterval(clockInterval);
  }, []);

  // 2. Station Welcome Announcement
  useEffect(() => {
    // Warm-up SpeechSynthesis
    const utter = new SpeechSynthesisUtterance("");
    window.speechSynthesis.speak(utter);

    setTimeout(() => {
      playDingDong();
      setTimeout(() => {
        speak("System informacji pasażerskiej uruchomiony pomyślnie.");
      }, 1200);
    }, 1000);
  }, []);

  // 3. Central Status Polling and Audio Alarms Loop
  useEffect(() => {
    const updateBoard = async () => {
      try {
        const res = await fetch(`${API}/status`);
        if (!res.ok) return;
        const data = await res.json();

        // Update zones state
        const currentZones = data.zones || {};
        setZones(currentZones);

        // Track which configured trains are not inside any zone ("W TRASIE")
        const occupiedTrainNames = Object.values(currentZones).filter(Boolean) as string[];
        const allTrains = ["Express", "Cargo"];
        const inRoute = allTrains.filter(name => !occupiedTrainNames.includes(name));
        setTrainsInRoute(inRoute);

        // ---- VOICE STATEMENT TRIGGER ENGINE ----
        Object.entries(currentZones).forEach(([z_id, occupant]) => {
          const prevOccupant = previousZonesRef.current[z_id];
          
          if (occupant && prevOccupant !== occupant) {
            playDingDong();
            setTimeout(() => {
              speak(`Uwaga podróżni. Pociąg ${occupant} wjechał na strefę numer ${z_id}. Prosimy zachować ostrożność.`);
            }, 1200);
          }
        });

        // Save layout snapshot to ref for edge delta computing
        previousZonesRef.current = currentZones;

      } catch (err) {
        console.error("Board pool error", err);
      }
    };

    updateBoard();
    const boardInterval = setInterval(updateBoard, 1500);
    return () => clearInterval(boardInterval);
  }, []);

  // 4. Web Audio API Station Gong Synthesizer
  const playDingDong = () => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      const ctx = audioContextRef.current;

      const playTone = (freq: number, startTime: number, duration: number) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, ctx.currentTime + startTime);
        gain.gain.setValueAtTime(0.4, ctx.currentTime + startTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + startTime + duration);
        osc.start(ctx.currentTime + startTime);
        osc.stop(ctx.currentTime + startTime + duration);
      };

      playTone(659.25, 0, 1.2);  // Note E5
      playTone(523.25, 0.5, 1.6); // Note C5
    } catch (e) {
      console.error("Audio context blocked by client interaction paradigm");
    }
  };

  // 5. Speech Synthesis Worker (TTS)
  const speak = (text: string) => {
    window.speechSynthesis.cancel();
    const msg = new SpeechSynthesisUtterance(text);
    msg.lang = "pl-PL";
    msg.rate = 0.82;
    msg.pitch = 0.95;
    window.speechSynthesis.speak(msg);
  };

  return (
    <div className="h-screen w-screen bg-[#001220] text-[#4da8da] font-mono p-4 md:p-8 flex flex-col items-center justify-center select-none antialiased">
      <div className="border-8 border-black rounded-2xl shadow-2xl bg-[#000c14] w-full max-w-7xl h-full flex flex-col p-6 overflow-hidden">
        
        {/* BOARD HEADER */}
        <div className="flex justify-between items-end border-b-4 border-[#4da8da] pb-4 mb-6">
          <div>
            <h1 className="text-4xl uppercase font-black tracking-widest text-[#4da8da] drop-shadow-[0_0_8px_rgba(77,168,218,0.8)]">
              STACJA GŁÓWNA FRMCS
            </h1>
            <p className="text-lg opacity-70 uppercase mt-1 tracking-wide font-sans font-bold">
              Przyjazdy i Odjazdy / Arrivals & Departures
            </p>
          </div>
          <div className="text-6xl font-bold tracking-wider text-[#4da8da] drop-shadow-[0_0_10px_rgba(77,168,218,0.8)]">
            {timeStr}
          </div>
        </div>

        {/* LED CONTENT MATRIX */}
        <div className="w-full flex-1 flex flex-col gap-4 overflow-y-auto pr-2">
          <div className="grid grid-cols-12 gap-4 text-xl font-black border-b border-[#4da8da]/30 pb-2 mb-2 opacity-60 tracking-widest uppercase">
            <div className="col-span-5">Pociąg / Train</div>
            <div className="col-span-4">Strefa / Zone</div>
            <div className="col-span-3 text-right">Status</div>
          </div>

          {/* ACTIVE OCCUPIED ZONES ROWS */}
          {Object.entries(zones)
            .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
            .map(([z_id, occupant]) => {
              if (!occupant) return null;
              return (
                <div key={z_id} className="grid grid-cols-12 gap-4 text-4xl border-b border-[#4da8da]/10 pb-4 items-center animate-pulse">
                  <div className="col-span-5 text-white flex items-center gap-3 font-bold tracking-wide">
                    <svg className="w-7 h-7 text-[#ffb703] drop-shadow-[0_0_5px_rgba(255,183,3,0.6)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                    </svg>
                    {occupant}
                  </div>
                  <div className="col-span-4 font-bold tracking-wide drop-shadow-[0_0_6px_rgba(77,168,218,0.7)]">
                    STREFA {z_id}
                  </div>
                  <div className="col-span-3 text-right text-[#ffb703] drop-shadow-[0_0_6px_rgba(255,183,3,0.7)] font-black tracking-widest">
                    WJEŻDŻA
                  </div>
                </div>
              );
            })}

          {/* TRAINS IN TRANSIT ROWS */}
          {trainsInRoute.map((name) => (
            <div key={name} className="grid grid-cols-12 gap-4 text-3xl border-b border-[#4da8da]/5 pb-4 items-center opacity-40">
              <div className="col-span-5 text-gray-400 font-bold tracking-wide">{name}</div>
              <div className="col-span-4 tracking-widest">W TRASIE...</div>
              <div className="col-span-3 text-right tracking-widest text-red-400/90">W DRODZE</div>
            </div>
          ))}
        </div>

        {/* LOWER MARQUEE ALERT TICKER */}
        <div className="mt-auto border-t-4 border-[#4da8da] pt-4 overflow-hidden whitespace-nowrap relative flex items-center bg-black/40 h-12 rounded">
          <div className="absolute left-0 inline-block text-2xl text-[#ffb703] font-bold tracking-widest uppercase drop-shadow-[0_0_6px_rgba(255,183,3,0.8)] animate-[marquee_25s_linear_infinite]">
            *** UWAGA PODRÓŻNI! PROSIMY NIE ZBLIŻAĆ SIĘ DO KRAWĘDZI MAKIETY. BAGGAGE LEFT UNATTENDED WILL BE DESTROYED. ZYCHAJĄC SKŁADY MOŻESZ USZKODZIĆ PRZEKŁADNIE LEGO LEGO TECHNIC. ***
          </div>
        </div>

      </div>

      {/* CSS TAILWIND INLINE MARQUEE KEYFRAMES DEFINITION */}
      <style jsx global>{`
        @keyframes marquee {
          0% { transform: translateX(70vw); }
          100% { transform: translateX(-100%); }
        }
      `}</style>
    </div>
  );
}
