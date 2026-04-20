"use client";

import { useState } from "react";
import { toast } from "react-hot-toast";
import { useEffect } from "react";


export default function Page() {
  const [expressConnected, setExpressConnected] = useState(false);
  const [cargoConnected, setCargoConnected] = useState(false);
  const [expressSpeed, setExpressSpeed] = useState(0);
  const [cargoSpeed, setCargoSpeed] = useState(0);
  const [expressLight, setExpressLight] = useState(false);
  const [status, setStatus] = useState<any>(null);

  const [mounted, setMounted] = useState(false);


  const API = process.env.NEXT_PUBLIC_HOST!;


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


  type TrainStatus = {
  speed: number;
  connected: boolean;
};

type StatusResponse = {
  express: TrainStatus;
  cargo: TrainStatus;
};



  // EXPRESS

  const connectExpress = async () => {
    const id = toast.loading("Connecting Express...");

    try {
      const res = await fetch(`${API}/express/connect`, { method: "POST" });
      
      await handleResponse(res);

      setExpressConnected(true);
      toast.success("Express connected");
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      toast.dismiss(id);
    }
  };

  const changeExpress = async (delta: number) => {
    const newSpeed = Math.max(-80, Math.min(80, expressSpeed + delta));
    setExpressSpeed(newSpeed);

    try {
      const res = await fetch(`${API}/express/speed`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ speed: newSpeed }),
      });

      await handleResponse(res);
      toast.success("Express speed updated");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  const stopExpress = async () => {
    try {
      const res = await fetch(`${API}/express/stop`, { method: "POST" });

      const data = await res.json();

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        setExpressSpeed(0);
        toast.success("Express stopped");
      }
    } catch {
      toast.error("Error stopping express");
    }
  };

  const setExpressLights = async (brightness: number) => {
    try {
      const res = await fetch(`${API}/express/light`, {
        method: "POST",
        headers: {
        "Content-Type": "application/json",
        },
        body: JSON.stringify({ brightness }),
      });

      const data = await res.json();

      if (!res.ok || data.status === "error") {
        throw new Error(data.message || "Error");
      }

      setExpressLight(brightness > 0);
      toast.success(`Light: ${data.brightness}`);
    } catch (err: any) {
      toast.error(err.message);
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
        setExpressLight(false);
        setExpressSpeed(0);
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

  const changeCargo = async (delta: number) => {
    const newSpeed = Math.max(-80, Math.min(80, cargoSpeed + delta));
    setCargoSpeed(newSpeed);

    try {
      const res = await fetch(`${API}/cargo/speed`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ speed: newSpeed }),
      });

      await handleResponse(res);
      toast.success("Cargo speed updated");
    } catch (err: any) {
      toast.error(err.message);
    }
  };

  const stopCargo = async () => {
    try {
      const res = await fetch(`${API}/cargo/stop`, { method: "POST" });

      const data = await res.json();

      if (data.status === "error") {
        toast.error(data.message);
      } else {
        setCargoSpeed(0);
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
        setCargoConnected(false);
        setCargoSpeed(0);
        toast.success("Cargo disconnected");
      }
    } catch {
      toast.dismiss(id);
      toast.error("Error disconnecting cargo");
    }
  };


  // STATUS

  const getStatus = async () => {
    try {
    const res = await fetch(`${API}/status`);
    const data = await res.json();

    if (!res.ok || data.status === "error") {
      throw new Error(data.message || "Error fetching status");
    }

    setStatus(data.data);

    setExpressConnected(data.data.express.connected);
    setCargoConnected(data.data.cargo.connected);
    setExpressLight(data.data.express.light);

  } catch (err: any) {
    toast.error(err.message);
  }
};

  if (!mounted) return null;

  return (
    <div className="space-y-10">
      <h1 className="text-3xl font-bold text-center">FRMCS Control Panel</h1>

      {/* EXPRESS */}
      <div className="bg-gray-800 text-white p-6 rounded-2xl shadow">
        <h2 className="text-xl mb-4">Express</h2>

        <div className="flex gap-2 flex-wrap">
          <button onClick={connectExpress} disabled={expressConnected} className="btn">Connect</button>
          <button onClick={disconnectExpress} disabled={!expressConnected} className="btn-red">Disconnect</button>
          <button onClick={stopExpress} disabled={!expressConnected} className="btn-yellow">STOP</button>
        </div>

        <div className="mt-4 flex gap-2">
          <button onClick={() => changeExpress(10)} disabled={!expressConnected} className="btn-green">Speed up</button>
          <button onClick={() => changeExpress(-10)} disabled={!expressConnected} className="btn-green">Slow down</button>
        </div>

        <p className="mt-2">Speed: {expressSpeed}</p>

        {/*<button onClick={changeExpress} className="btn mt-2">
          Apply
        </button>*/}

        <div className="mt-4 flex gap-2">
          <button onClick={() => setExpressLights(100)} disabled={!expressConnected || expressLight} className="btn">Lights ON</button>
          <button onClick={() => setExpressLights(0)} disabled={!expressConnected || !expressLight} className="btn">Lights OFF</button>
        </div>

      </div>

      {/* CARGO */}
      <div className="bg-gray-800 text-white p-6 rounded-2xl shadow">
        <h2 className="text-xl mb-4">Cargo</h2>

        <div className="flex gap-2 flex-wrap">
          <button onClick={connectCargo} disabled={cargoConnected} className="btn">Connect</button>
          <button onClick={disconnectCargo} disabled={!cargoConnected} className="btn-red">Disconnect</button>
          <button onClick={stopCargo} disabled={!cargoConnected} className="btn-yellow">STOP</button>
        </div>

        <div className="mt-4 flex gap-2">
          <button onClick={() => changeCargo(10)} disabled={!cargoConnected} className="btn-green">Speed up</button>
          <button onClick={() => changeCargo(-10)} disabled={!cargoConnected} className="btn-green">Slow down</button>
        </div>

        <p className="mt-2">Speed: {cargoSpeed}</p>

        {/*<button onClick={setCargo} className="btn mt-2">
          Apply
        </button>*/}
        {/* Lights */}
      </div>

      {/* STATUS */}
      <div className="bg-white p-4 rounded text-sm space-y-2">
        <div>
          Express:{" "}
          <span className={expressConnected ? "text-green-400" : "text-red-400"}>
            {expressConnected ? "Connected" : "Disconnected"}
          </span>{" "}
          | Speed: {expressSpeed}
        </div>

        <div>
          Cargo:{" "}
          <span className={cargoConnected ? "text-green-400" : "text-red-400"}>
            {cargoConnected ? "Connected" : "Disconnected"}
          </span>{" "}
          | Speed: {cargoSpeed}
        </div>
      </div>
    </div>
  );
}
