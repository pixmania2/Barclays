import React, { useState } from "react";
import { UserServicePanel } from "./services/UserService";
import { RestaurantServicePanel } from "./services/RestaurantService";
import { OrderServicePanel } from "./services/OrderService";
import { PaymentServicePanel } from "./services/PaymentService";
import { DeliveryServicePanel } from "./services/DeliveryService";
import { NotificationServicePanel } from "./services/NotificationService";

export default function App() {
  const [logs, setLogs] = useState([]);
  const [fireCount, setFireCount] = useState(1);
  const [delay, setDelay] = useState(0);
  const [errorRate, setErrorRate] = useState(0); // ✅ new

  const logMessage = (message) => {
    setLogs((prev) => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] ${message}`,
    ]);
  };

  const clearLogs = () => setLogs([]);

  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

  const randomFire = async () => {
    const all = [
      ...Object.values(UserServicePanel.api || {}),
      ...Object.values(RestaurantServicePanel.api || {}),
      ...Object.values(OrderServicePanel.api || {}),
      ...Object.values(PaymentServicePanel.api || {}),
      ...Object.values(DeliveryServicePanel.api || {}),
      ...Object.values(NotificationServicePanel.api || {}),
    ];
    for (let i = 0; i < fireCount; i++) {
      const randomFn = all[Math.floor(Math.random() * all.length)];
      await randomFn(logMessage, errorRate); // pass errorRate to spam handlers
      if (delay > 0) await sleep(delay);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <h1 className="text-3xl font-bold mb-4 text-blue-700">
        API Firepower Panel 🚀
      </h1>

      {/* 🔥 Global controls */}
      <div className="mb-6 p-4 bg-white rounded shadow flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-sm font-medium">🔥 Fire Count</label>
          <input
            type="number"
            className="border rounded p-1 text-sm w-24"
            min={1}
            value={fireCount}
            onChange={(e) => setFireCount(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="block text-sm font-medium">⏱ Delay (ms)</label>
          <input
            type="number"
            className="border rounded p-1 text-sm w-24"
            min={0}
            value={delay}
            onChange={(e) => setDelay(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="block text-sm font-medium">⚠️ Error Rate (%)</label>
          <input
            type="number"
            className="border rounded p-1 text-sm w-24"
            min={0}
            max={100}
            value={errorRate}
            onChange={(e) => setErrorRate(Number(e.target.value))}
          />
        </div>
        <button
          onClick={randomFire}
          className="bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded text-sm"
        >
          💣 Random Spam
        </button>
      </div>

      {/* ⚙️ API Panels */}
      <div className="grid md:grid-cols-2 gap-6">
        <UserServicePanel
          log={logMessage}
          fireCount={fireCount}
          delay={delay}
          errorRate={errorRate}
        />
        <RestaurantServicePanel
          log={logMessage}
          fireCount={fireCount}
          delay={delay}
          errorRate={errorRate}
        />
        <OrderServicePanel
          log={logMessage}
          fireCount={fireCount}
          delay={delay}
          errorRate={errorRate}
        />
        <PaymentServicePanel
          log={logMessage}
          fireCount={fireCount}
          delay={delay}
          errorRate={errorRate}
        />
        <DeliveryServicePanel
          log={logMessage}
          fireCount={fireCount}
          delay={delay}
          errorRate={errorRate}
        />
        <NotificationServicePanel
          log={logMessage}
          fireCount={fireCount}
          delay={delay}
          errorRate={errorRate}
        />
      </div>

      {/* 🧾 Console Logs */}
      <div className="mt-8 bg-black text-white p-4 rounded-lg h-64 overflow-y-auto shadow-md">
        <div className="flex justify-between items-center mb-2">
          <span className="font-semibold text-green-400">
            📜 Console Output
          </span>
          <button
            onClick={clearLogs}
            className="bg-red-500 hover:bg-red-700 text-white text-xs px-3 py-1 rounded"
          >
            Clear Logs
          </button>
        </div>
        <pre className="text-sm whitespace-pre-wrap">{logs.join("\n")}</pre>
      </div>
    </div>
  );
}
