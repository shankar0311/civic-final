import React, { useState } from 'react';
import api from '../api';
import { useAuth } from "../contexts/AuthContext";

function ReportForm() {
  const { token } = useAuth();
  const [formData, setFormData] = useState({
    title: "",
    description: "",
    latitude: 40.7128, // Default NYC
    longitude: -74.006,
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (!token) {
        setError("You must be logged in to submit a report");
        setLoading(false);
        return;
      }

      const response = await api.post("/reports/", formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      alert("Report submitted successfully!");
      // Reset form
      setFormData({
        title: "",
        description: "",
        latitude: 40.7128,
        longitude: -74.006,
      });
    } catch (error) {
      console.error("Error submitting report:", error);
      const errorMsg =
        error.response?.data?.detail ||
        error.message ||
        "Failed to submit report. Please try again.";
      setError(errorMsg);
      alert(`Error: ${errorMsg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto bg-white p-6 rounded shadow">
      <h2 className="text-2xl font-bold mb-4">Submit a Road Report</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block mb-1">Title</label>
          <input
            type="text"
            className="w-full border p-2 rounded"
            value={formData.title}
            onChange={(e) =>
              setFormData({ ...formData, title: e.target.value })
            }
            required
          />
        </div>
        <div>
          <label className="block mb-1">Description</label>
          <textarea
            className="w-full border p-2 rounded"
            value={formData.description}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            required
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block mb-1">Latitude</label>
            <input
              type="number"
              step="any"
              className="w-full border p-2 rounded"
              value={formData.latitude}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  latitude: parseFloat(e.target.value),
                })
              }
              required
            />
          </div>
          <div>
            <label className="block mb-1">Longitude</label>
            <input
              type="number"
              step="any"
              className="w-full border p-2 rounded"
              value={formData.longitude}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  longitude: parseFloat(e.target.value),
                })
              }
              required
            />
          </div>
        </div>
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}
        <button
          type="submit"
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700 disabled:bg-gray-400"
          disabled={loading}
        >
          {loading ? "Submitting..." : "Submit"}
        </button>
      </form>
    </div>
  );
}

export default ReportForm;
