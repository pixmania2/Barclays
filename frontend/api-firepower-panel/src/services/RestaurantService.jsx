import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function RestaurantServicePanel({
  log,
  fireCount = 1,
  delay = 0,
  errorRate = 0,
}) {
  const [restaurantId, setRestaurantId] = useState("");
  const [menuItemId, setMenuItemId] = useState("");

  const baseUrl = "http://localhost:5002/api/restaurants";
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
          finalUrl = baseUrl + "/invalid-path"; // unexpected 404
        } else {
          payload = { broken: true }; // malformed body
        }
      }

      try {
        const res = await axios({ method, url: finalUrl, data: payload });
        log(`${label} ✅ (${res.status}): ${finalUrl}`);
        if (res.data?.restaurant?.id) setRestaurantId(res.data.restaurant.id);
        if (res.data?.menu_item?.id) setMenuItemId(res.data.menu_item.id);
      } catch (err) {
        log(`${label} ❌ (${err.response?.status || "ERR"}): ${finalUrl}`);
      }
      if (delay > 0) await sleep(delay);
    }
  };

  const handleRandom = async () => {
    const options = [
      () =>
        fire("post", baseUrl, "Create", () => ({
          name: "Resto " + uuidv4().slice(0, 5),
          location: "Nowhere",
        })),
      () => fire("get", baseUrl, "List", () => null),
      () => fire("get", `${baseUrl}/${restaurantId}`, "Get", () => null),
      () =>
        fire("patch", `${baseUrl}/${restaurantId}/update`, "Update", () => ({
          name: "Updated " + uuidv4().slice(0, 5),
        })),
      () =>
        fire("get", `${baseUrl}/${restaurantId}/menu`, "Get Menu", () => null),
      () =>
        fire("post", `${baseUrl}/${restaurantId}/menu/add`, "Add Menu", () => ({
          name: "Item " + uuidv4().slice(0, 4),
          price: Math.random() * 50 + 10,
        })),
      () =>
        fire(
          "patch",
          `${baseUrl}/${restaurantId}/menu/update`,
          "Update Menu",
          () => ({
            id: menuItemId,
            name: "Modified",
            price: 99,
          })
        ),
    ];

    for (let i = 0; i < fireCount; i++) {
      const random = options[Math.floor(Math.random() * options.length)];
      await random();
      if (delay > 0) await sleep(delay);
    }
  };

  return (
    <div className="bg-white shadow-md rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-2 text-orange-600">
        🍽 Restaurant Service
      </h2>
      <div className="space-y-2">
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire("post", baseUrl, "Create", () => ({
              name: "Resto " + uuidv4().slice(0, 4),
              location: "City Center",
            }))
          }
        >
          Create Restaurant
        </button>
        <button
          className="bg-green-600 text-white px-3 py-1 rounded"
          onClick={() => fire("get", baseUrl, "List", () => null)}
        >
          List Restaurants
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire("get", `${baseUrl}/${restaurantId}`, "Get", () => null)
          }
          disabled={!restaurantId}
        >
          Get Restaurant
        </button>
        <button
          className="bg-purple-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "patch",
              `${baseUrl}/${restaurantId}/update`,
              "Update",
              () => ({
                name: "Updated " + uuidv4().slice(0, 4),
                location: "New Location",
              })
            )
          }
          disabled={!restaurantId}
        >
          Update Restaurant
        </button>
        <button
          className="bg-teal-600 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "get",
              `${baseUrl}/${restaurantId}/menu`,
              "Get Menu",
              () => null
            )
          }
          disabled={!restaurantId}
        >
          Get Menu
        </button>
        <button
          className="bg-indigo-500 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "post",
              `${baseUrl}/${restaurantId}/menu/add`,
              "Add Menu",
              () => ({
                name: "Item " + uuidv4().slice(0, 3),
                price: Math.floor(Math.random() * 100),
              })
            )
          }
          disabled={!restaurantId}
        >
          Add Menu Item
        </button>
        <button
          className="bg-pink-600 text-white px-3 py-1 rounded"
          onClick={() =>
            fire(
              "patch",
              `${baseUrl}/${restaurantId}/menu/update`,
              "Update Menu",
              () => ({
                id: menuItemId,
                name: "Updated Dish",
                price: 49.99,
              })
            )
          }
          disabled={!restaurantId || !menuItemId}
        >
          Update Menu Item
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
