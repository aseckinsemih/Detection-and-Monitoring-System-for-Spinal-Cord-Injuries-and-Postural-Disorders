import { useState } from "react"
import { PatientService } from "../services/api"

function AddPatientForm({ onAdded }) {
  const [form, setForm] = useState({
    firstName: "", lastName: "", dateOfBirth: "", gender: "Female",
    diagnosisType: "Idiopathic", curveLocation: "Thoracic",
    rissersSign: 0, initialCobbAngle: 0, treatmentPlan: "Observation",
    braceType: "", braceHoursPerDay: 0, physicalTherapy: false
  })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!form.firstName || !form.lastName) return alert("Please enter first and last name")
    setSubmitting(true)
    try {
      await PatientService.create(form)
      alert("Patient added successfully!")
      onAdded()
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message))
    } finally {
      setSubmitting(false)
    }
  }

  const input = (label, key, type = "text") => (
    <div style={{ marginBottom: 14 }}>
      <label style={{ fontSize: 13, color: "#555", display: "block", marginBottom: 4 }}>{label}</label>
      <input type={type} value={form[key]}
        onChange={e => setForm({ ...form, [key]: type === "number" ? +e.target.value : e.target.value })}
        style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #ddd", fontSize: 14 }} />
    </div>
  )

  const select = (label, key, options) => (
    <div style={{ marginBottom: 14 }}>
      <label style={{ fontSize: 13, color: "#555", display: "block", marginBottom: 4 }}>{label}</label>
      <select value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })}
        style={{ width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #ddd", fontSize: 14 }}>
        {options.map(o => <option key={o}>{o}</option>)}
      </select>
    </div>
  )

  return (
    <div style={{ padding: 24, maxWidth: 600, overflowY: "auto", height: "100%" }}>
      <h2 style={{ marginBottom: 20 }}>Add New Patient</h2>

      <div style={{ background: "#f9f9f9", borderRadius: 8, padding: 16, marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, color: "#555", marginBottom: 14 }}>Personal Info</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {input("First Name", "firstName")}
          {input("Last Name", "lastName")}
        </div>
        {input("Date of Birth", "dateOfBirth", "date")}
        {select("Gender", "gender", ["Female", "Male", "Other"])}
      </div>

      <div style={{ background: "#f9f9f9", borderRadius: 8, padding: 16, marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, color: "#555", marginBottom: 14 }}>Diagnosis</h3>
        {select("Diagnosis Type", "diagnosisType", ["Idiopathic", "Congenital", "Neuromuscular"])}
        {select("Curve Location", "curveLocation", ["Thoracic", "Lumbar", "Thoracolumbar"])}
        {input("Risser Sign (0–5)", "rissersSign", "number")}
        {input("Initial Cobb Angle (°)", "initialCobbAngle", "number")}
      </div>

      <div style={{ background: "#f9f9f9", borderRadius: 8, padding: 16, marginBottom: 20 }}>
        <h3 style={{ fontSize: 14, color: "#555", marginBottom: 14 }}>Treatment</h3>
        {select("Treatment Plan", "treatmentPlan", ["Observation", "Bracing", "Physical Therapy", "Surgery"])}
        {form.treatmentPlan === "Bracing" && <>
          {input("Brace Type (e.g. Boston Brace)", "braceType")}
          {input("Brace Hours Per Day", "braceHoursPerDay", "number")}
        </>}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
          <input type="checkbox" checked={form.physicalTherapy}
            onChange={e => setForm({ ...form, physicalTherapy: e.target.checked })} />
          <label style={{ fontSize: 13, color: "#555" }}>Physical Therapy</label>
        </div>
      </div>

      <button onClick={handleSubmit} disabled={submitting}
        style={{
          background: submitting ? "#a5b4fc" : "#4f46e5",
          color: "white",
          border: "none",
          padding: "10px 28px",
          borderRadius: 8,
          fontSize: 14,
          cursor: submitting ? "not-allowed" : "pointer"
        }}>
        {submitting ? "Saving..." : "Save Patient"}
      </button>
    </div>
  )
}

export default AddPatientForm