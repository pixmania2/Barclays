import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function OrderServicePanel({ log }) {
  const [orderId, setOrderId] = useState("");
  const [userId] = useState(uuidv4());
  const [restaurantId] = useState(uuidv4());
  const [bulkCount, setBulkCount] = useState(1);

  const baseUrl = "http://localhost:5003/api/orders";

  const send = async (method, url, body = null, label = "") => {
    try {
      const res = await axios({ method, url, data: body });
      log(`${label} ✅ (${res.status}): ${url}`);
      if (label.includes("Create Order")) setOrderId(res.data.order.id);
    } catch (err) {
      log(`${label} ❌ (${err.response?.status || "ERR"}): ${url}`);
    }
  };

  const createOrderPayload = () => ({
    userId,
    restaurantId,
    items: ["Burger", "Fries", "Soda"],
  });

  const bulkCreate = async () => {
    for (let i = 0; i < bulkCount; i++) {
      await send(
        "post",
        `${baseUrl}/create`,
        createOrderPayload(),
        "Create Order"
      );
    }
  };

  return (
    <div className="bg-white shadow-md rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-2 text-green-700">
        🧾 Order Service
      </h2>

      <div className="space-y-2">
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
          onClick={() =>
            send(
              "post",
              `${baseUrl}/create`,
              createOrderPayload(),
              "Create Order"
            )
          }
        >
          Create Order
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600"
          onClick={() =>
            send("get", `${baseUrl}/${orderId}`, null, "Get Order")
          }
          disabled={!orderId}
        >
          Get Order
        </button>
        <button
          className="bg-purple-500 text-white px-3 py-1 rounded hover:bg-purple-600"
          onClick={() =>
            send(
              "patch",
              `${baseUrl}/${orderId}/update_status`,
              { status: "PREPARING" },
              "Update Status"
            )
          }
          disabled={!orderId}
        >
          Update Status
        </button>
        <button
          className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
          onClick={() =>
            send("patch", `${baseUrl}/${orderId}/cancel`, null, "Cancel Order")
          }
          disabled={!orderId}
        >
          Cancel Order
        </button>
        <button
          className="bg-indigo-500 text-white px-3 py-1 rounded hover:bg-indigo-600"
          onClick={() =>
            send("get", `${baseUrl}/user/${userId}`, null, "User Orders")
          }
        >
          Get Orders by User
        </button>
        <button
          className="bg-teal-500 text-white px-3 py-1 rounded hover:bg-teal-600"
          onClick={() =>
            send("post", `${baseUrl}/${orderId}/reorder`, null, "Reorder")
          }
          disabled={!orderId}
        >
          Reorder
        </button>
      </div>

      <div className="my-2">
        <label className="text-sm font-medium">Bulk Create:</label>
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
            onClick={bulkCreate}
          >
            Fire Create x {bulkCount}
          </button>
        </div>
      </div>
    </div>
  );
}

