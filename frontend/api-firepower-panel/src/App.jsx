import React, { useState } from "react";
import { UserServicePanel } from "./services/UserService";
import { RestaurantServicePanel } from "./services/RestaurantService";
import { OrderServicePanel } from "./services/OrderService";
import { PaymentServicePanel } from "./services/PaymentService";
import { DeliveryServicePanel } from "./services/DeliveryService";
import { NotificationServicePanel } from "./services/NotificationService";

export default function App() {
  const [logs, setLogs] = useState([]);

  const logMessage = (message) => {
    setLogs((prev) => [
      ...prev,
      `[${new Date().toLocaleTimeString()}] ${message}`,
    ]);
  };

  const clearLogs = () => setLogs([]);

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <h1 className="text-3xl font-bold mb-4 text-blue-700">
        API Firepower Panel 🚀
      </h1>

      <div className="grid md:grid-cols-2 gap-6">
        <UserServicePanel log={logMessage} />
        <RestaurantServicePanel log={logMessage} />
        <OrderServicePanel log={logMessage} />
        <PaymentServicePanel log={logMessage} />
        <DeliveryServicePanel log={logMessage} />
        <NotificationServicePanel log={logMessage} />
      </div>

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
        <pre className="text-sm">{logs.join("\n")}</pre>
      </div>
    </div>
  );
}
