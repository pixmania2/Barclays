import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function UserServicePanel({
  log,
  fireCount = 1,
  delay = 0,
  errorRate = 0,
}) {
  const [userId, setUserId] = useState("");
  const [payload, setPayload] = useState({
    name: "John Doe",
    email: "john@example.com",
  });

  const apiBase = "http://localhost:5001/api/users";
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const shouldError = () => Math.random() * 100 < errorRate;

  const fire = async (method, url, body = null, label = "") => {
    for (let i = 0; i < fireCount; i++) {
      const isError = shouldError();
      let finalUrl = url;
      let finalBody = body;
      let logPrefix = label;

      if (isError) {
        logPrefix = `⚠️ ${label}`;
        // Expected error payloads
        if (url.includes("/register")) {
          finalBody = { email: "" }; // missing name
        } else if (url.includes("/login")) {
          finalBody = { email: "wrong@example.com", password: "nope" }; // bad login
        } else if (url.includes("/update")) {
          finalBody = { name: "" }; // invalid name
        }

        // Unexpected error: change URL to something broken
        if (Math.random() < 0.5) {
          finalUrl = `${apiBase}/nonexistent`;
        }
      }

      try {
        const response = await axios({
          method,
          url: finalUrl,
          data: finalBody,
        });
        log(`${logPrefix} ✅ (${response.status}): ${finalUrl}`);
        if (response.data.user?.id) setUserId(response.data.user.id);
      } catch (err) {
        log(`${logPrefix} ❌ (${err.response?.status || "ERR"}): ${finalUrl}`);
      }

      if (delay > 0) await sleep(delay);
    }
  };

  const handleRandom = async () => {
    const handlers = Object.entries(UserServicePanel.api || {});
    for (let i = 0; i < fireCount; i++) {
      const [label, fn] = handlers[Math.floor(Math.random() * handlers.length)];
      log(`🎲 Random User API (${i + 1}): ${label}`);
      await fn(log, errorRate);
      if (delay > 0) await sleep(delay);
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
            fire("post", `${apiBase}/register`, payload, "Register")
          }
        >
          Register
        </button>
        <button
          className="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600"
          onClick={() => fire("post", `${apiBase}/login`, payload, "Login")}
        >
          Login
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600"
          onClick={() => fire("get", `${apiBase}/${userId}`, null, "Get User")}
          disabled={!userId}
        >
          Get User
        </button>
        <button
          className="bg-purple-500 text-white px-3 py-1 rounded hover:bg-purple-600"
          onClick={() =>
            fire(
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
        <button
          className="bg-black text-white px-3 py-1 rounded hover:bg-gray-800"
          onClick={handleRandom}
        >
          🎲 Random
        </button>
      </div>

      <textarea
        className="w-full text-sm p-2 border mt-4 rounded font-mono"
        rows={5}
        value={JSON.stringify(payload, null, 2)}
        onChange={(e) => {
          try {
            setPayload(JSON.parse(e.target.value));
          } catch {
            // Ignore parsing errors
          }
        }}
      />
    </div>
  );
}

// For use in Random Spam
UserServicePanel.api = {
  register: async (log, errorRate = 0) => {
    const isError = Math.random() * 100 < errorRate;
    const url = "http://localhost:5001/api/users/register";
    const payload = isError
      ? { email: "" } // expected error
      : {
          name: "User " + uuidv4().slice(0, 5),
          email: `${uuidv4().slice(0, 5)}@example.com`,
        };

    try {
      const res = await axios.post(isError ? `${url}BROKEN` : url, payload);
      log(`${isError ? "⚠️ Register" : "Register"} ✅ (${res.status})`);
    } catch (err) {
      log(
        `${isError ? "⚠️ Register" : "Register"} ❌ (${
          err.response?.status || "ERR"
        })`
      );
    }
  },

  login: async (log, errorRate = 0) => {
    const isError = Math.random() * 100 < errorRate;
    const url = "http://localhost:5001/api/users/login";
    const payload = isError
      ? { email: "invalid@example.com", password: "wrong" }
      : { email: "john@example.com", password: "123456" };

    try {
      const res = await axios.post(isError ? `${url}BROKEN` : url, payload);
      log(`${isError ? "⚠️ Login" : "Login"} ✅ (${res.status})`);
    } catch (err) {
      log(
        `${isError ? "⚠️ Login" : "Login"} ❌ (${
          err.response?.status || "ERR"
        })`
      );
    }
  },
};
