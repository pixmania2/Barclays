import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function PaymentServicePanel({ log }) {
  const [txId, setTxId] = useState("");
  const [orderId] = useState(uuidv4());
  const [bulkCount, setBulkCount] = useState(1);

  const baseUrl = "http://localhost:5004/api/payments";

  const send = async (method, url, body = null, label = "") => {
    try {
      const res = await axios({ method, url, data: body });
      log(`${label} ✅ (${res.status}): ${url}`);
      if (label.includes("Charge")) setTxId(res.data.transaction_id);
    } catch (err) {
      log(`${label} ❌ (${err.response?.status || "ERR"}): ${url}`);
    }
  };

  const chargePayload = () => ({
    orderId,
    amount: parseFloat((Math.random() * 100 + 10).toFixed(2)),
  });

  const bulkCharge = async () => {
    for (let i = 0; i < bulkCount; i++) {
      await send("post", `${baseUrl}/charge`, chargePayload(), "Charge");
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
            send("post", `${baseUrl}/charge`, chargePayload(), "Charge")
          }
        >
          Charge
        </button>
        <button
          className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
          onClick={() =>
            send("post", `${baseUrl}/refund`, { transactionId: txId }, "Refund")
          }
          disabled={!txId}
        >
          Refund
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600"
          onClick={() =>
            send("get", `${baseUrl}/${txId}`, null, "Get Transaction")
          }
          disabled={!txId}
        >
          Get Transaction
        </button>
        <button
          className="bg-purple-500 text-white px-3 py-1 rounded hover:bg-purple-600"
          onClick={() =>
            send(
              "patch",
              `${baseUrl}/${txId}/update_status`,
              { status: "FAILED" },
              "Update Status"
            )
          }
          disabled={!txId}
        >
          Update Status
        </button>
      </div>

      <div className="my-2">
        <label className="text-sm font-medium">Bulk Charge:</label>
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
            onClick={bulkCharge}
          >
            Fire Charge x {bulkCount}
          </button>
        </div>
      </div>
    </div>
  );
}
