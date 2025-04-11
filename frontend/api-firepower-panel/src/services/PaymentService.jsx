import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function PaymentServicePanel({
  log,
  fireCount = 1,
  delay = 0,
  errorRate = 0,
}) {
  const [txId, setTxId] = useState("");
  const [orderId] = useState(uuidv4());

  const baseUrl = "http://localhost:5004/api/payments";
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
          finalUrl = `${baseUrl}/invalid`; // unexpected endpoint
        } else {
          payload = { invalid: "broken" }; // expected bad input
        }
      }

      try {
        const res = await axios({ method, url: finalUrl, data: payload });
        log(`${label} ✅ (${res.status}): ${finalUrl}`);
        if (label.includes("Charge") && res.data.transaction_id) {
          setTxId(res.data.transaction_id);
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
        fire("post", `${baseUrl}/charge`, "Charge", () => ({
          orderId,
          amount: parseFloat((Math.random() * 100 + 10).toFixed(2)),
        })),
      () =>
        fire("post", `${baseUrl}/refund`, "Refund", () => ({
          transactionId: txId,
        })),
      () => fire("get", `${baseUrl}/${txId}`, "Get Transaction", () => null),
      () =>
        fire(
          "patch",
          `${baseUrl}/${txId}/update_status`,
          "Update Status",
          () => ({
            status: "FAILED",
          })
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
      <h2 className="text-lg font-semibold mb-2 text-pink-600">
        💳 Payment Service
      </h2>

      <div className="space-y-2">
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
          onClick={() =>
            fire("post", `${baseUrl}/charge`, "Charge", () => ({
              orderId,
              amount: parseFloat((Math.random() * 100 + 10).toFixed(2)),
            }))
          }
        >
          Charge
        </button>
        <button
          className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
          onClick={() =>
            fire("post", `${baseUrl}/refund`, "Refund", () => ({
              transactionId: txId,
            }))
          }
          disabled={!txId}
        >
          Refund
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600"
          onClick={() =>
            fire("get", `${baseUrl}/${txId}`, "Get Transaction", () => null)
          }
          disabled={!txId}
        >
          Get Transaction
        </button>
        <button
          className="bg-purple-500 text-white px-3 py-1 rounded hover:bg-purple-600"
          onClick={() =>
            fire(
              "patch",
              `${baseUrl}/${txId}/update_status`,
              "Update Status",
              () => ({
                status: "FAILED",
              })
            )
          }
          disabled={!txId}
        >
          Update Status
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
