import { useState } from "react"
import { PatientService } from "../services/api"

function PhotoUpload({ patient, onDone }) {
  const [preview, setPreview] = useState(patient.photo || null)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleFile = (e) => {
    const f = e.target.files[0]
    if (!f) return
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  const handleUpload = async () => {
    if (!file) return alert("Please select a photo first")
    setLoading(true)
    try {
      await PatientService.uploadPhoto(patient._id, file)
      alert("Photo uploaded successfully! Click OK to refresh.")
      onDone()
    } catch (e) {
      alert("Error uploading photo: " + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 400 }}>
      <h2 style={{ marginBottom: 6 }}>Patient Photo</h2>
      <p style={{ color: "#888", fontSize: 14, marginBottom: 20 }}>
        {patient.firstName} {patient.lastName}
      </p>

      <div style={{
        width: 160, height: 160, borderRadius: "50%", overflow: "hidden",
        background: "#f0f0f0", marginBottom: 20, display: "flex",
        alignItems: "center", justifyContent: "center", border: "2px dashed #ddd"
      }}>
        {preview
          ? <img src={preview} alt="Patient" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          : <span style={{ color: "#bbb", fontSize: 13 }}>No photo</span>
        }
      </div>

      <label style={{
        display: "inline-block", padding: "8px 20px", borderRadius: 8,
        border: "1px solid #ddd", cursor: "pointer", fontSize: 14,
        marginBottom: 14, background: "#f9f9f9"
      }}>
        Choose Photo
        <input type="file" accept="image/*" onChange={handleFile} style={{ display: "none" }} />
      </label>

      {file && (
        <p style={{ fontSize: 12, color: "#888", marginBottom: 14 }}>
          Selected: {file.name}
        </p>
      )}

      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={handleUpload} disabled={loading}
          style={{
            background: loading ? "#a5b4fc" : "#4f46e5", color: "white",
            border: "none", padding: "10px 24px", borderRadius: 8,
            fontSize: 14, cursor: loading ? "not-allowed" : "pointer"
          }}>
          {loading ? "Uploading..." : "Save Photo"}
        </button>
        <button onClick={onDone}
          style={{
            background: "white", color: "#555", border: "1px solid #ddd",
            padding: "10px 24px", borderRadius: 8, fontSize: 14, cursor: "pointer"
          }}>
          Cancel
        </button>
      </div>
    </div>
  )
}

export default PhotoUpload