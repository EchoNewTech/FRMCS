"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export default function Page() {
  const [status, setStatus] = useState<any>(null);
  const [mounted, setMounted] = useState(false);

  const API = process.env.NEXT_PUBLIC_HOST!;

  useEffect(() => {
    setMounted(true);
    const interval = setInterval(getStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const getStatus = async () => {
    try {
      const res = await fetch(`${API}/status`);
      if (!res.ok) throw new Error("Backend connection failed");
      const data = await res.json();
      setStatus(data);
    } catch (err: any) {
      console.error(err.message);
    }
  };

  if (!mounted) return null;
  if (!status) return <div className="p-6 text-white text-center">Loading system status...</div>;

  return (
    <div className="space-y-6 p-6 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-center text-white">FRMCS Control Panel</h1>

      <div className="flex flex-col gap-6">
        {["express", "cargo"].map((train) => {
          // DOSTĘP DO DANYCH PRZEZ status.trains
          const trainData = status.trains?.[train];
          const isConnected = trainData?.connected;

          return (
            <Link key={train} href={`/${train}`}>
              <div className="bg-gray-800 text-white p-6 rounded-2xl shadow cursor-pointer hover:bg-gray-700 transition-colors border border-gray-700">
                <h2 className="text-xl capitalize mb-2 font-bold">{train}</h2>

                <p>
                  {isConnected ? (
                    <span className="text-green-400 font-semibold">Connected</span>
                  ) : (
                    <span className="text-red-400">Disconnected</span>
                  )}{" "}
                  | Speed: {trainData?.speed || 0}%
                </p>

                <p className="text-sm text-gray-400 mt-1">
                  Section: <span className="text-blue-400 font-mono">{trainData?.section || "Disconnected"}</span>
                </p>
              </div>
            </Link>
          );
        })}
      </div>

      {/* DZIENNIK DYSPOZYTORA (LOGI) */}
      <div className="mt-8 bg-black/40 p-4 rounded-xl border border-gray-700 shadow-inner">
        <h3 className="text-gray-500 text-xs font-bold mb-3 uppercase tracking-widest flex items-center">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse mr-2"></span> Dispatcher Logs
        </h3>
        <ul className="text-sm font-mono text-blue-300 space-y-1 h-32 overflow-y-auto pl-2">
            {status.logs?.map((log: string, i: number) => (
                <li key={i} className="border-l border-blue-900 pl-2 opacity-90">{`> ${log}`}</li>
            ))}
            {(!status.logs || status.logs.length === 0) && <li className="text-gray-600">No logs available...</li>}
        </ul>
      </div>
    </div>
  );
}
