"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "react-hot-toast";

export default function TrainPage() {
  const params = useParams();
  const train = params.train as string;

  const API = process.env.NEXT_PUBLIC_HOST!;

  const [connected, setConnected] = useState(false);
  const [speed, setSpeed] = useState(0);
  const [light, setLight] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    getStatus();
  }, []);

  const handleResponse = async (res: Response) => {
    const data = await res.json();

    if (!res.ok || data.status === "error") {
      throw new Error(data.message || "Request failed");
    }

    return data;
  };

  const getStatus = async () => {
    try {
      const res = await fetch(`${API}/status`);
      const data = await res.json();

      if (!res.ok || data.status === "error") {
        throw new Error(data.message);
      }

      const t = data.data[train];

      setConnected(t.connected);
      setSpeed(t.speed);
      setLight(t.light);
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  // CONNECT
  const connect = async () => {
    const id = toast.loading(`Connecting ${train}...`);

    try {
      const res = await fetch(`${API}/${train}/connect`, { method: "POST" });
      await handleResponse(res);

      setConnected(true);
      toast.success(`${train} connected`);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      toast.dismiss(id);
    }
  };

  // DISCONNECT
  const disconnect = async () => {
    const id = toast.loading("Disconnecting...");

    try {
      const res = await fetch(`${API}/${train}/disconnect`, { method: "POST" });
      await handleResponse(res);

      setConnected(false);
      setSpeed(0);
      setLight(false);

      toast.success(`${train} disconnected`);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      toast.dismiss(id);
    }
  };

  // SPEED
  const changeSpeed = async (delta: number) => {
    const newSpeed = Math.max(-80, Math.min(80, speed + delta));
    setSpeed(newSpeed);

    try {
      const res = await fetch(`${API}/${train}/speed`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ speed: newSpeed }),
      });

      await handleResponse(res);
      toast.success("Speed updated");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  // STOP
  const stop = async () => {
    try {
      const res = await fetch(`${API}/${train}/stop`, {
        method: "POST",
      });

      await handleResponse(res);

      setSpeed(0);
      toast.success("Stopped");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  // LIGHT
  const setLights = async (brightness: number) => {
    try {
      const res = await fetch(`${API}/${train}/light`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ brightness }),
      });

      await handleResponse(res);

      setLight(brightness > 0);
      toast.success("Lights updated");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  if (!mounted) return null;

  if (!["express", "cargo"].includes(train)) {
    return <div>Not found</div>;
  }

  return (
    <div className="space-y-10 p-6">
      <h1 className="text-3xl font-bold capitalize text-center">
        {train}
      </h1>

      <div className="bg-gray-800 text-white p-6 rounded-2xl shadow">
        <div className="flex gap-2 flex-wrap">
          <button onClick={connect} disabled={connected} className="btn">
            Connect
          </button>
          <button onClick={disconnect} disabled={!connected} className="btn-red">
            Disconnect
          </button>
          <button onClick={stop} disabled={!connected} className="btn-yellow">
            STOP
          </button>
        </div>

        <div className="mt-4 flex gap-2">
          <button onClick={() => changeSpeed(10)} disabled={!connected} className="btn-green">
            Speed up
          </button>
          <button onClick={() => changeSpeed(-10)} disabled={!connected} className="btn-green">
            Slow down
          </button>
        </div>

        {train === "express" && (
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => setLights(100)}
              disabled={!connected || light}
              className="btn"
            >
              Lights ON
            </button>
            <button
              onClick={() => setLights(0)}
              disabled={!connected || !light}
              className="btn"
            >
              Lights OFF
            </button>
          </div>
        )}

        <div className="text-center text-lg space-x-2">
            <span>
                Status:{" "}
                <span className={connected ? "text-green-400" : "text-red-400"}>
                    {connected ? "Connected" : "Disconnected"}
                </span>
            </span>
            <span>| Speed: {speed}</span>
        </div>

      </div>
    </div>
  );
}
