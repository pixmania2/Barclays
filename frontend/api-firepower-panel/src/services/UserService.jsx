import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function UserServicePanel({ log }) {
  const [userId, setUserId] = useState("");
  const [bulkCount, setBulkCount] = useState(1);
  const [payload, setPayload] = useState({
    name: "John Doe",
    email: "john@example.com",
  });

  const apiBase = "http://localhost:5001/api/users";

  const sendRequest = async (method, url, body = null, label = "") => {
    try {
      const response = await axios({ method, url, data: body });
      log(`${label} ✅ (${response.status}): ${url}`);
      if (response.data.user?.id) setUserId(response.data.user.id);
    } catch (err) {
        console.error(err);
      log(`${label} ❌ (${err.response?.status || "ERR"}): ${url}`);
    }
  };

  const bulkTrigger = async (handler, count) => {
    for (let i = 0; i < count; i++) {
      await handler();
    }
  };

  return (
    <div className="bg-white shadow-md rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-2 text-blue-600">
        👤 User Service
      </h2>

      <div className="mb-2 space-y-2">
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
          onClick={() =>
            sendRequest("post", `${apiBase}/register`, payload, "Register")
          }
        >
          Register
        </button>
        <button
          className="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600"
          onClick={() =>
            sendRequest("post", `${apiBase}/login`, payload, "Login")
          }
        >
          Login
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600"
          onClick={() =>
            sendRequest("get", `${apiBase}/${userId}`, null, "Get User")
          }
          disabled={!userId}
        >
          Get User
        </button>
        <button
          className="bg-purple-500 text-white px-3 py-1 rounded hover:bg-purple-600"
          onClick={() =>
            sendRequest(
              "patch",
              `${apiBase}/${userId}/update`,
              { name: "Updated Name" },
              "Update"
            )
          }
          disabled={!userId}
        >
          Update User
        </button>
      </div>

      <div className="my-2">
        <label className="text-sm font-medium">Bulk Trigger:</label>
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
            onClick={() =>
              bulkTrigger(
                () =>
                  sendRequest(
                    "post",
                    `${apiBase}/register`,
                    {
                      name: `User ${uuidv4().slice(0, 5)}`,
                      email: `${uuidv4().slice(0, 5)}@example.com`,
                      password: "123456",
                    },
                    "Bulk Register"
                  ),
                bulkCount
              )
            }
          >
            Fire Register x {bulkCount}
          </button>
        </div>
      </div>

      <textarea
        className="w-full text-sm p-2 border mt-4 rounded font-mono"
        rows={5}
        value={JSON.stringify(payload, null, 2)}
        onChange={(e) => {
          try {
            setPayload(JSON.parse(e.target.value));
          } catch {
            // ignore parse errors
          }
        }}
      />
    </div>
  );
}
