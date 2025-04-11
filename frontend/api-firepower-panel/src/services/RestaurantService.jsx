import React, { useState } from "react";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";

export function RestaurantServicePanel({ log }) {
  const [restaurantId, setRestaurantId] = useState("");
  const [menuItemId, setMenuItemId] = useState("");
  const [bulkCount, setBulkCount] = useState(1);

  const baseUrl = "http://localhost:5002/api/restaurants";

  const randomRestaurant = () => ({
    name: "Restaurant " + uuidv4().slice(0, 5),
    location: "City Center",
  });

  const randomMenuItem = () => ({
    name: "Dish " + uuidv4().slice(0, 4),
    price: parseFloat((Math.random() * 20 + 5).toFixed(2)),
  });

  const send = async (method, url, body = null, label = "") => {
    try {
      const res = await axios({ method, url, data: body });
      log(`${label} ✅ (${res.status}): ${url}`);
      if (label.includes("Create Restaurant"))
        setRestaurantId(res.data.restaurant.id);
      if (label.includes("Add Menu")) setMenuItemId(res.data.menu_item?.id);
    } catch (err) {
      log(`${label} ❌ (${err.response?.status || "ERR"}): ${url}`);
    }
  };

  const bulkCreate = async () => {
    for (let i = 0; i < bulkCount; i++) {
      await send("post", baseUrl, randomRestaurant(), "Create Restaurant");
    }
  };

  return (
    <div className="bg-white shadow-md rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-2 text-orange-600">
        🍽 Restaurant Service
      </h2>

      <div className="space-y-2">
        <button
          className="bg-orange-500 text-white px-3 py-1 rounded hover:bg-orange-600"
          onClick={() => send("get", baseUrl, null, "List Restaurants")}
        >
          List Restaurants
        </button>
        <button
          className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
          onClick={() =>
            send("post", baseUrl, randomRestaurant(), "Create Restaurant")
          }
        >
          Create Restaurant
        </button>
        <button
          className="bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600"
          onClick={() =>
            send("get", `${baseUrl}/${restaurantId}`, null, "Get Restaurant")
          }
          disabled={!restaurantId}
        >
          Get Restaurant
        </button>
        <button
          className="bg-yellow-500 text-white px-3 py-1 rounded hover:bg-yellow-600"
          onClick={() =>
            send(
              "patch",
              `${baseUrl}/${restaurantId}/update`,
              {
                name: "Updated " + uuidv4().slice(0, 3),
                location: "New Area",
              },
              "Update Restaurant"
            )
          }
          disabled={!restaurantId}
        >
          Update Restaurant
        </button>

        <div className="pt-2 border-t">
          <button
            className="bg-purple-500 text-white px-3 py-1 rounded hover:bg-purple-600"
            onClick={() =>
              send("get", `${baseUrl}/${restaurantId}/menu`, null, "Get Menu")
            }
            disabled={!restaurantId}
          >
            Get Menu
          </button>
          <button
            className="bg-teal-500 text-white px-3 py-1 rounded hover:bg-teal-600"
            onClick={() =>
              send(
                "post",
                `${baseUrl}/${restaurantId}/menu/add`,
                randomMenuItem(),
                "Add Menu Item"
              )
            }
            disabled={!restaurantId}
          >
            Add Menu Item
          </button>
          <button
            className="bg-indigo-500 text-white px-3 py-1 rounded hover:bg-indigo-600"
            onClick={() =>
              send(
                "patch",
                `${baseUrl}/${restaurantId}/menu/update`,
                {
                  id: menuItemId,
                  name: "Updated Dish",
                  price: 18.99,
                },
                "Update Menu Item"
              )
            }
            disabled={!restaurantId || !menuItemId}
          >
            Update Menu Item
          </button>
          <button
            className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
            onClick={() =>
              send(
                "delete",
                `${baseUrl}/${restaurantId}/menu/${menuItemId}`,
                null,
                "Delete Menu Item"
              )
            }
            disabled={!restaurantId || !menuItemId}
          >
            Delete Menu Item
          </button>
        </div>
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
