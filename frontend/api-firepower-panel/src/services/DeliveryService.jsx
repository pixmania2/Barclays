import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function DeliveryServicePanel({
  log,
  fireCount = 1,
  delay = 0,
  errorRate = 0,
}) {
  const [deliveryId, setDeliveryId] = useState("");
  const [orderId] = useState(uuidv4());
  const [driverId] = useState("driver_" + uuidv4().slice(0, 5));

  const baseUrl = "http://localhost:5005/api/deliveries";
  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
  const shouldError = () => Math.random() * 100 < errorRate;

  const fire = async (method, url, label, dataFn) => {
    for (let i = 0; i < fireCount; i++) {
      let isError = shouldError();
      let finalUrl = url;
      let payload = dataFn();

      if (isError) {
        label = `⚠️ ${label}`;
        if (Math.random() < 0.5) {
          finalUrl = `${baseUrl}/invalid-${uuidv4().slice(0, 4)}`; // unexpected
        } else {
          payload = { invalid: "true" }; // expected bad input
        }
      }

      try {
        const response = await axios({ method, url: finalUrl, data: payload });
        log(`${label} ✅ (${response.status}): ${finalUrl}`);
        if (label.includes("Create") && response.data?.delivery_id) {
          setDeliveryId(response.data.delivery_id);
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
        fire("post", `${baseUrl}/create`, "Create", () => ({
          orderId: uuidv4(),
          driverId: "driver_" + uuidv4().slice(0, 4),
        })),
      () => fire("get", `${baseUrl}/${deliveryId}`, "Get", () => null),
      () =>
        fire(
          "patch",
          `${baseUrl}/${deliveryId}/update_status`,
          "Update Status",
          () => ({
            status: "IN_TRANSIT",
          })
        ),
      () =>
        fire(
          "patch",
          `${baseUrl}/${deliveryId}/update_location`,
          "Update Location",
          () => ({
            location: "Sector 21B",
          })
        ),
      () =>
        fire("patch", `${baseUrl}/${deliveryId}/reassign`, "Reassign", () => ({
          driverId: "driver_" + uuidv4().slice(0, 5),
        })),
      () =>
        fire(
          "get",
          `${baseUrl}/${deliveryId}/tracking`,
          "Tracking",
          () => null
        ),
      () =>
        fire(
          "patch",
          `${baseUrl}/${deliveryId}/mark_delivered`,
          "Mark Delivered",
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
      <h2 className="text-lg font-semibold mb-2 text-cyan-700">
        🚚 Delivery Service
      </h2>

      <div className="space-y-2">
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire("post", `${baseUrl}/create`, "Create", () => ({
              orderId,
              driverId,
            }))
          }
        >
          Create Delivery
        </button>
        <button
          className="bg-green-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire("get", `${baseUrl}/${deliveryId}`, "Get Delivery", () => null)
          }
          disabled={!deliveryId}
        >
          Get Delivery
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "patch",
              `${baseUrl}/${deliveryId}/update_status`,
              "Update Status",
              () => ({
                status: "IN_TRANSIT",
              })
            )
          }
          disabled={!deliveryId}
        >
          Update Status
        </button>
        <button
          className="bg-teal-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "patch",
              `${baseUrl}/${deliveryId}/update_location`,
              "Update Location",
              () => ({
                location: "Sector 45, Metro City",
              })
            )
          }
          disabled={!deliveryId}
        >
          Update Location
        </button>
        <button
          className="bg-purple-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "patch",
              `${baseUrl}/${deliveryId}/reassign`,
              "Reassign",
              () => ({
                driverId: "driver_" + uuidv4().slice(0, 4),
              })
            )
          }
          disabled={!deliveryId}
        >
          Reassign
        </button>
        <button
          className="bg-gray-600 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "get",
              `${baseUrl}/${deliveryId}/tracking`,
              "Tracking",
              () => null
            )
          }
          disabled={!deliveryId}
        >
          Track Delivery
        </button>
        <button
          className="bg-red-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "patch",
              `${baseUrl}/${deliveryId}/mark_delivered`,
              "Mark Delivered",
              () => null
            )
          }
          disabled={!deliveryId}
        >
          Mark Delivered
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
