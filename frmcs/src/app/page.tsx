"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "react-hot-toast";

export default function Page() {
  const [status, setStatus] = useState<any>(null);
  const [mounted, setMounted] = useState(false);

  const API = process.env.NEXT_PUBLIC_HOST!;

  useEffect(() => {
    setMounted(true);
    getStatus();
  }, []);

  const getStatus = async () => {
    try {
      const res = await fetch(`${API}/status`);
      const data = await res.json();

      if (!res.ok || data.status === "error") {
        throw new Error(data.message);
      }

      setStatus(data.data);
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  if (!mounted) return null;
  if (!status) return <div>Loading...</div>;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-3xl font-bold text-center">FRMCS Control Panel</h1>
      <div className="flex flex-col gap-6">
        {["express", "cargo"].map((train) => (
          <Link key={train} href={`/${train}`}>
            <div className="bg-gray-800 text-white p-6 rounded-2xl shadow cursor-pointer hover:bg-gray-700">
              <h2 className="text-xl capitalize mb-2">{train}</h2>

              <p>
                {status[train].connected ? "Connected" : "Disconnected"} | Speed:{" "}
                {status[train].speed}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
