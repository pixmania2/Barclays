import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";


export function DeliveryServicePanel({ log }) {
  const [deliveryId, setDeliveryId] = useState("");
  const [orderId] = useState(uuidv4());
  const [driverId] = useState("driver_" + uuidv4().slice(0, 5));
  const [bulkCount, setBulkCount] = useState(1);

  const baseUrl = "http://localhost:5005/api/deliveries";

  const send = async (method, url, body = null, label = "") => {
    try {
      const res = await axios({ method, url, data: body });
      log(`${label} ✅ (${res.status}): ${url}`);
      if (label.includes("Create")) setDeliveryId(res.data.delivery_id);
    } catch (err) {
      log(`${label} ❌ (${err.response?.status || "ERR"}): ${url}`);
    }
  };

  const bulkCreate = async () => {
    for (let i = 0; i < bulkCount; i++) {
      await send(
        "post",
        `${baseUrl}/create`,
        {
          orderId: uuidv4(),
          driverId: "driver_" + uuidv4().slice(0, 5),
        },
        "Create Delivery"
      );
    }
  };

  return (
    <div className="bg-white shadow-md rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-2 text-cyan-700">
        🚚 Delivery Service
      </h2>

      <div className="space-y-2">
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
          onClick={() =>
            send(
              "post",
              `${baseUrl}/create`,
              {
                orderId,
                driverId,
              },
              "Create Delivery"
            )
          }
        >
          Create Delivery
        </button>
        <button
          className="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600"
          onClick={() =>
            send("get", `${baseUrl}/${deliveryId}`, null, "Get Delivery")
          }
          disabled={!deliveryId}
        >
          Get Delivery
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600"
          onClick={() =>
            send(
              "patch",
              `${baseUrl}/${deliveryId}/update_status`,
              {
                status: "IN_TRANSIT",
              },
              "Update Status"
            )
          }
          disabled={!deliveryId}
        >
          Update Status
        </button>
        <button
          className="bg-teal-500 text-white px-3 py-1 rounded hover:bg-teal-600"
          onClick={() =>
            send(
              "patch",
              `${baseUrl}/${deliveryId}/update_location`,
              {
                location: "Sector 45, Metro City",
              },
              "Update Location"
            )
          }
          disabled={!deliveryId}
        >
          Update Location
        </button>
        <button
          className="bg-purple-500 text-white px-3 py-1 rounded hover:bg-purple-600"
          onClick={() =>
            send(
              "patch",
              `${baseUrl}/${deliveryId}/reassign`,
              {
                driverId: "driver_" + uuidv4().slice(0, 4),
              },
              "Reassign"
            )
          }
          disabled={!deliveryId}
        >
          Reassign
        </button>
        <button
          className="bg-gray-600 text-white px-3 py-1 rounded hover:bg-gray-700"
          onClick={() =>
            send("get", `${baseUrl}/${deliveryId}/tracking`, null, "Tracking")
          }
          disabled={!deliveryId}
        >
          Track Delivery
        </button>
        <button
          className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
          onClick={() =>
            send(
              "patch",
              `${baseUrl}/${deliveryId}/mark_delivered`,
              null,
              "Mark Delivered"
            )
          }
          disabled={!deliveryId}
        >
          Mark Delivered
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
            className="bg-black text-white text-sm px-2 py-1 rounded hover:bg-gray-800"
            onClick={bulkCreate}
          >
            Fire Create x {bulkCount}
          </button>
        </div>
      </div>
    </div>
  );
}
