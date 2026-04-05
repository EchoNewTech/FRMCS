"use client";

import { useState } from "react";
import { toast } from "react-hot-toast";


export default function Page() {
  const [expressConnected, setExpressConnected] = useState(false);
  const [cargoConnected, setCargoConnected] = useState(false);
  const [expressSpeed, setExpressSpeed] = useState(0);
  const [cargoSpeed, setCargoSpeed] = useState(0);
  const [status, setStatus] = useState<any>(null);

  const API = "http://localhost:8000";


  // EXPRESS

  const connectExpress = async () => {
    const id = toast.loading("Connecting Express...");

    try {
      const res = await fetch(`${API}/express/connect`, { method: "POST" });
      
      const data = await res.json();

      toast.dismiss(id);

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        setExpressConnected(true);
        toast.success("Express connected");
      }
    } catch (err) {
      toast.dismiss(id);
      toast.error("Error connecting express");
    }
  };

  const setExpress = async () => {
    try {
      const res = await fetch(`${API}/express/speed?speed=${expressSpeed}`, { method: "POST" });

      const data = await res.json();

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        toast.success("Express speed updated");
      }
    } catch {
      toast.error("Error setting express speed");
    }
  };

  const stopExpress = async () => {
    try {
      const res = await fetch(`${API}/express/stop`, { method: "POST" });

      const data = await res.json();

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        toast.success("Express stopped");
      }
    } catch {
      toast.error("Error stopping express");
    }
  };

  const disconnectExpress = async () => {
    const id = toast.loading("Disconnecting...");

    try {
      const res = await fetch(`${API}/express/disconnect`, { method: "POST" });
      
      const data = await res.json();

      toast.dismiss(id);

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        setExpressConnected(false);
        toast.success("Express disconnected");
      }
    } catch {
      toast.dismiss(id);
      toast.error("Error disconnecting express");
    }
  };


  // CARGO

  const connectCargo = async () => {
    const id = toast.loading("Connecting Cargo...");

    try {
      const res = await fetch(`${API}/cargo/connect`, { method: "POST" });
      const data = await res.json();

      toast.dismiss(id);

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        setCargoConnected(true);
        toast.success("Cargo connected");
      }
    } catch (err) {
      toast.dismiss(id);
      toast.error("Error connecting cargo");
    }
  };

  const setCargo = async () => {
    try {
      const res = await fetch(`${API}/cargo/speed?speed=${cargoSpeed}`, { method: "POST" });

      const data = await res.json();

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        toast.success("Cargo speed updated");
      }
    } catch {
      toast.error("Error setting cargo speed");
    }
  };

  const stopCargo = async () => {
    try {
      const res = await fetch(`${API}/cargo/stop`, { method: "POST" });

      const data = await res.json();

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        toast.success("Cargo stopped");
      }
    } catch {
      toast.error("Error stopping cargo");
    }
  };

  const disconnectCargo = async () => {
    const id = toast.loading("Disconnecting...");

    try {
      const res = await fetch(`${API}/cargo/disconnect`, { method: "POST" });

      const data = await res.json();

      toast.dismiss(id);

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        setExpressConnected(false);
        toast.success("Cargo disconnected");
      }
    } catch {
      toast.dismiss(id);
      toast.error("Error disconnecting cargo");
    }
  };


  // STATUS

  const getStatus = async () => {
    const res = await fetch(`${API}/status`);

    const data = await res.json();

    if (data.status === "error") {
      alert("Error: " + data.message);
    } else {
      alert("Disconnected");
    }

    setStatus(data);
  };


  return (
    <div className="space-y-10">
      <h1 className="text-3xl font-bold text-center">FRMCS Control Panel</h1>

      {/* EXPRESS */}
      <div className="bg-gray-800 text-white p-6 rounded-2xl shadow">
        <h2 className="text-xl mb-4">Express</h2>

        <div className="flex gap-2 flex-wrap">
          <button onClick={connectExpress} disabled={expressConnected} className="btn">Connect</button>
          <button onClick={disconnectExpress} disabled={!expressConnected} className="btn bg-red-500">Disconnect</button>
          <button onClick={stopExpress} disabled={!expressConnected} className="btn bg-yellow-500">STOP</button>
        </div>

        <div className="mt-4">
          <input
            type="range"
            min="-80"
            max="80"
            value={expressSpeed}
            onChange={(e) => setExpressSpeed(Number(e.target.value))}
            className="w-full"
          />
          <p>Speed: {expressSpeed}</p>
          <button onClick={setExpress} className="btn mt-2">Set Speed</button>
        </div>
      </div>

      {/* CARGO */}
      <div className="bg-gray-800 text-white p-6 rounded-2xl shadow">
        <h2 className="text-xl mb-4">Cargo</h2>

        <div className="flex gap-2 flex-wrap">
          <button onClick={connectCargo} disabled={cargoConnected} className="btn">Connect</button>
          <button onClick={disconnectCargo} disabled={!cargoConnected} className="btn bg-red-500">Disconnect</button>
          <button onClick={stopCargo} disabled={!cargoConnected} className="btn bg-yellow-500">STOP</button>
        </div>

        <div className="mt-4">
          <input
            type="range"
            min="-80"
            max="80"
            value={cargoSpeed}
            onChange={(e) => setCargoSpeed(Number(e.target.value))}
            className="w-full"
          />
          <p>Speed: {cargoSpeed}</p>
          <button onClick={setCargo} className="btn mt-2">Set Speed</button>
        </div>
      </div>

      {/* STATUS */}
      <div className="bg-gray-900 text-white p-6 rounded-2xl shadow">
        <h2 className="text-xl mb-4">Status</h2>

        <button onClick={getStatus} className="btn mb-4">
          Refresh
        </button>

        {status && (
          <pre className="bg-black p-4 rounded text-sm overflow-auto">
            {JSON.stringify(status, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
