import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function NotificationServicePanel({
  log,
  fireCount = 1,
  delay = 0,
  errorRate = 0,
}) {
  const [userId] = useState(uuidv4());
  const [notificationId, setNotificationId] = useState("");

  const baseUrl = "http://localhost:5006/api/notifications";
  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
  const shouldError = () => Math.random() * 100 < errorRate;

  const fire = async (method, url, label, dataFn) => {
    for (let i = 0; i < fireCount; i++) {
      let finalUrl = url;
      let payload = dataFn();
      const isError = shouldError();

      if (isError) {
        label = `⚠️ ${label}`;
        if (Math.random() < 0.5) {
          finalUrl = `${baseUrl}/oops-${uuidv4().slice(0, 4)}`; // broken endpoint
        } else {
          payload = { invalid: true }; // malformed
        }
      }

      try {
        const res = await axios({ method, url: finalUrl, data: payload });
        log(`${label} ✅ (${res.status}): ${finalUrl}`);
        if (label.includes("Send") && res.data.notification?.id) {
          setNotificationId(res.data.notification.id);
        }
      } catch (err) {
        log(`${label} ❌ (${err.response?.status || "ERR"}): ${finalUrl}`);
      }

      if (delay > 0) await sleep(delay);
    }
  };

  const handleRandom = async () => {
    const options = [
      () =>
        fire("post", `${baseUrl}/send`, "Send", () => ({
          userId,
          message: "🚀 New update " + uuidv4().slice(0, 4),
          type: "info",
        })),
      () => fire("get", `${baseUrl}/user/${userId}`, "Get by User", () => null),
      () =>
        fire(
          "patch",
          `${baseUrl}/${notificationId}/read`,
          "Mark Read",
          () => null
        ),
    ];

    for (let i = 0; i < fireCount; i++) {
      const fn = options[Math.floor(Math.random() * options.length)];
      await fn();
      if (delay > 0) await sleep(delay);
    }
  };

  return (
    <div className="bg-white shadow-md rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-2 text-red-600">
        🔔 Notification Service
      </h2>

      <div className="space-y-2">
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire("post", `${baseUrl}/send`, "Send Notification", () => ({
              userId,
              message: "New message " + uuidv4().slice(0, 4),
              type: "info",
            }))
          }
        >
          Send Notification
        </button>
        <button
          className="bg-green-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "get",
              `${baseUrl}/user/${userId}`,
              "Get Notifications",
              () => null
            )
          }
        >
          Get Notifications by User
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "patch",
              `${baseUrl}/${notificationId}/read`,
              "Mark as Read",
              () => null
            )
          }
          disabled={!notificationId}
        >
          Mark as Read
        </button>
        <button
          className="bg-black text-white px-3 py-1 rounded"
          onClick={handleRandom}
        >
          🎲 Random
        </button>
      </div>
    </div>
  );
}
