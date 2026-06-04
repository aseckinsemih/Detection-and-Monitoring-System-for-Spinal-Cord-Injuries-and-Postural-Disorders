import { useState, useEffect } from "react"
import PatientList from "./components/PatientList"
import PatientDetail from "./components/PatientDetail"
import AddPatientForm from "./components/AddPatientForm"
import AddVisitForm from "./components/AddVisitForm"
import EditPatientForm from "./components/EditPatientForm"
import PhotoUpload from "./components/PhotoUpload"
import { PatientService } from "./services/api"

function App() {
  const [patients, setPatients] = useState([])
  const [selected, setSelected] = useState(null)
  const [view, setView] = useState("detail")
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchPatients = async () => {
    setLoading(true)
    try {
      const data = await PatientService.getAll()
      setPatients(data)
      setError(null)
    } catch (err) {
      setError("Failed to load patients list: " + err.message)
    } finally {
      setLoading(false)
    }
  }

  const refreshSelected = async (id) => {
    try {
      const data = await PatientService.getById(id)
      setSelected(data)
      await fetchPatients()
    } catch (err) {
      alert("Error refreshing patient details: " + err.message)
    }
  }

  useEffect(() => { fetchPatients() }, [])

  const btnStyle = (active) => ({
    padding: "6px 16px", borderRadius: 6, border: "1px solid #ddd", cursor: "pointer",
    background: active ? "#4f46e5" : "white", color: active ? "white" : "#333", fontSize: 14
  })

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      <PatientList patients={patients} selected={selected}
        onSelect={p => { setSelected(p); setView("detail") }} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ borderBottom: "1px solid #eee", padding: "12px 24px", display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button style={btnStyle(view === "detail")} onClick={() => setView("detail")}>Patient Detail</button>
          <button style={btnStyle(view === "add")} onClick={() => setView("add")}>+ Add Patient</button>
          {selected && <>
            <button style={btnStyle(view === "visit")} onClick={() => setView("visit")}>+ Add Visit</button>
            <button style={btnStyle(view === "edit")} onClick={() => setView("edit")}>Edit Patient</button>
            <button style={btnStyle(view === "photo")} onClick={() => setView("photo")}>📷 Photo</button>
            <button style={{ ...btnStyle(false), marginLeft: "auto" }}
              onClick={() => alert("Report feature coming soon!")}>Report</button>
            <button
              onClick={async () => {
                if (!window.confirm(`Delete ${selected.firstName} ${selected.lastName}? This cannot be undone.`)) return
                try {
                  await PatientService.delete(selected._id)
                  setSelected(null)
                  setView("detail")
                  fetchPatients()
                } catch (err) {
                  alert("Failed to delete patient: " + err.message)
                }
              }}
              style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid #fca5a5", cursor: "pointer", background: "white", color: "#dc2626", fontSize: 14 }}>
              Delete Patient
            </button>
          </>}
        </div>
        {error && (
          <div style={{ background: "#fee2e2", color: "#991b1b", padding: "8px 24px", fontSize: 14 }}>
            {error}
          </div>
        )}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading && patients.length === 0 ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#888" }}>
              Loading patient data...
            </div>
          ) : (
            <>
              {view === "detail" && <PatientDetail patient={selected} />}
              {view === "add" && <AddPatientForm onAdded={() => { fetchPatients(); setView("detail") }} />}
              {view === "visit" && selected && <AddVisitForm patient={selected}
                onDone={() => { refreshSelected(selected._id); setView("detail") }} />}
              {view === "edit" && selected && <EditPatientForm patient={selected}
                onDone={() => { refreshSelected(selected._id); setView("detail") }} />}
              {view === "photo" && selected && <PhotoUpload patient={selected}
                onDone={async () => { await refreshSelected(selected._id); setView("detail") }} />}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default App