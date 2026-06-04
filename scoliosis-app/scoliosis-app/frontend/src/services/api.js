import axios from "axios";

// Environment-aware dynamic configuration fallback to local development URL
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const PatientService = {
  getAll: () => apiClient.get("/patients").then(res => res.data),
  getById: (id) => apiClient.get(`/patients/${id}`).then(res => res.data),
  create: (data) => apiClient.post("/patients", { ...data, visits: data.visits || [] }).then(res => res.data),
  update: (id, data) => {
    // Exclude database metadata if it was added to prevent Pydantic parsing issues
    const { _id, ...cleanData } = data;
    return apiClient.put(`/patients/${id}`, cleanData).then(res => res.data);
  },
  delete: (id) => apiClient.delete(`/patients/${id}`).then(res => res.data),
  addVisit: (id, visitData) => apiClient.post(`/patients/${id}/visits`, visitData).then(res => res.data),
  uploadPhoto: (id, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post(`/patients/${id}/photo`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then(res => res.data);
  },
  getLatestTelemetry: (patientId) => apiClient.get(`/telemetry/${patientId}/latest`).then(res => res.data)
};

export default apiClient;
