"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { toast } from "react-hot-toast";

export default function TrainPage() {
  const params = useParams();
  const router = useRouter();
  const train = params.train as string;

  const API = process.env.NEXT_PUBLIC_HOST!;

  const [connected, setConnected] = useState(false);
  const [speed, setSpeed] = useState(0);
  const [currentSection, setCurrentSection] = useState("none");
  const [mounted, setMounted] = useState(false);
  
  // Funkcjonalna poprawka: Flaga blokująca przyciski podczas trwania zapytania
  const [isPending, setIsPending] = useState(false);
  // Funkcjonalna poprawka: Ref do wstrzymania odświeżania podczas komend
  const isPollingPaused = useRef(false);

  useEffect(() => {
    setMounted(true);
    getStatus();
    const interval = setInterval(() => {
      if (!isPollingPaused.current) getStatus();
    }, 500);
    return () => clearInterval(interval);
  }, []);

  const getStatus = async () => {
    try {
      const res = await fetch(`${API}/${train}/position`);
      const data = await res.json();
      if (!res.ok || data.status === "error") return;

      const d = data.data;
      setConnected(d.connected);
      setSpeed(d.speed);
      setCurrentSection(d.section); 
    } catch (err: any) {
      console.warn("Status fetch failed");
    }
  };

  const sendCommand = async (endpoint: string, body?: any) => {
    setIsPending(true);
    isPollingPaused.current = true; // Wstrzymaj polling, żeby nie nadpisał stanu 
    
    try {
      const res = await fetch(`${API}/${train}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });

      const data = await res.json();
      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Request failed");
      }
      
      // Po udanej komendzie odśwież dane, zanim włączysz polling
      await getStatus();
      return data;
    } finally {
      setIsPending(false);
      isPollingPaused.current = false;
    }
  };

  const connect = async () => {
    const id = toast.loading("Connecting...");
    try {
      await sendCommand("connect");
      toast.success("Connected", { id });
    } catch (err: any) {
      toast.error(err.message, { id });
    }
  };

  const disconnect = async () => {
    const id = toast.loading("Disconnecting...");
    try {
      await sendCommand("disconnect");
      toast.success("Disconnected", { id });
    } catch (err: any) {
      toast.error(err.message, { id });
    }
  };

  const changeSpeed = async (delta: number) => {
    const newSpeed = Math.max(-80, Math.min(80, speed + delta));
    setSpeed(newSpeed);
    try {
      await sendCommand("speed", { speed: newSpeed });
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  const stop = async () => {
    try {
      await sendCommand("stop");
      toast.success("Stopped");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  if (!mounted) return null;

  return (
    <div className="space-y-6 p-6 text-white">
      <button 
        onClick={() => router.push("/")}
        className="text-gray-400 hover:text-white transition-colors"
      >
        ← Back to Dashboard
      </button>

      <h1 className="text-3xl font-bold capitalize">{train} Control</h1>

      <div className="bg-gray-800 p-6 rounded-2xl shadow border border-gray-700">
        <div className="flex justify-between items-center mb-6">
          <p className="text-lg">
            Status:{" "}
            <span className={connected ? "text-green-400 font-bold" : "text-red-400 font-bold"}>
              {connected ? "Connected" : "Disconnected"}
            </span>
          </p>
          <p className="text-lg font-mono">
            Speed: <span className="text-yellow-400">{speed}%</span>
          </p>
        </div>

        <div className="bg-gray-900 p-4 rounded-xl mb-6 border border-gray-700">
          <p className="text-sm text-gray-400 uppercase tracking-widest">Current Section</p>
          <p className="text-2xl font-bold text-blue-400">{currentSection}</p>
        </div>

        <div className="flex gap-4 flex-wrap">
          <button 
            onClick={connect} 
            disabled={connected || isPending} 
            className={`px-4 py-2 rounded-lg font-bold ${(!connected && !isPending) ? 'bg-green-600 hover:bg-green-500' : 'bg-gray-600 cursor-not-allowed'}`}
          >
            {isPending && !connected ? "Linking..." : "Connect"}
          </button>

          <button 
            onClick={disconnect} 
            disabled={!connected || isPending} 
            className={`px-4 py-2 rounded-lg font-bold ${(connected && !isPending) ? 'bg-red-600 hover:bg-red-500' : 'bg-gray-600 cursor-not-allowed'}`}
          >
            Disconnect
          </button>

          <button 
            onClick={stop} 
            disabled={!connected || isPending} 
            className={`px-4 py-2 rounded-lg font-bold ${(connected && !isPending) ? 'bg-yellow-600 hover:bg-yellow-500' : 'bg-gray-600 cursor-not-allowed'}`}
          >
            EMERGENCY STOP
          </button>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-700">
          <p className="text-sm text-gray-400 mb-4 uppercase tracking-widest">Manual Speed Control</p>
          <div className="flex gap-4">
            <button
              onClick={() => changeSpeed(10)}
              disabled={!connected || isPending}
              className={`flex-1 py-3 rounded-xl font-bold transition-colors ${(connected && !isPending) ? 'bg-blue-600 hover:bg-blue-500' : 'bg-gray-600 cursor-not-allowed'}`}
            >
              Increase (+10)
            </button>

            <button
              onClick={() => changeSpeed(-10)}
              disabled={!connected || isPending}
              className={`flex-1 py-3 rounded-xl font-bold transition-colors ${(connected && !isPending) ? 'bg-blue-600 hover:bg-blue-500' : 'bg-gray-600 cursor-not-allowed'}`}
            >
              Decrease (-10)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
