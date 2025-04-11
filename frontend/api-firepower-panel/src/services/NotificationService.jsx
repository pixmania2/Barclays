import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function NotificationServicePanel({ log }) {
  const [userId] = useState(uuidv4());
  const [notificationId, setNotificationId] = useState("");
  const [bulkCount, setBulkCount] = useState(1);

  const baseUrl = "http://localhost:5006/api/notifications";

  const send = async (method, url, body = null, label = "") => {
    try {
      const res = await axios({ method, url, data: body });
      log(`${label} ✅ (${res.status}): ${url}`);
      if (label.includes("Send")) setNotificationId(res.data.notification.id);
    } catch (err) {
      log(`${label} ❌ (${err.response?.status || "ERR"}): ${url}`);
    }
  };

  const createNotification = () => ({
    userId,
    message: "🚀 New order update: " + uuidv4().slice(0, 4),
    type: "info",
  });

  const bulkSend = async () => {
    for (let i = 0; i < bulkCount; i++) {
      await send("post", `${baseUrl}/send`, createNotification(), "Send");
    }
  };

  return (
    <div className="bg-white shadow-md rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-2 text-red-600">
        🔔 Notification Service
      </h2>

      <div className="space-y-2">
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
          onClick={() =>
            send(
              "post",
              `${baseUrl}/send`,
              createNotification(),
              "Send Notification"
            )
          }
        >
          Send Notification
        </button>
        <button
          className="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600"
          onClick={() =>
            send("get", `${baseUrl}/user/${userId}`, null, "Get Notifications")
          }
        >
          Get Notifications by User
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600"
          onClick={() =>
            send(
              "patch",
              `${baseUrl}/${notificationId}/read`,
              null,
              "Mark as Read"
            )
          }
          disabled={!notificationId}
        >
          Mark as Read
        </button>
      </div>

      <div className="my-2">
        <label className="text-sm font-medium">Bulk Send:</label>
        <div className="flex items-center gap-2 mt-1">
          <input
            type="number"
            className="border p-1 w-16 text-sm rounded"
            value={bulkCount}
            min={1}
            onChange={(e) => setBulkCount(Number(e.target.value))}
          />
          <button
            className="bg-gray-800 text-white text-sm px-2 py-1 rounded hover:bg-gray-700"
            onClick={bulkSend}
          >
            Fire Send x {bulkCount}
          </button>
        </div>
      </div>
    </div>
  );
}
