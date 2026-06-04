function PatientList({ patients, selected, onSelect }) {
  return (
    <div style={{ width: 260, borderRight: "1px solid #eee", height: "100vh", overflowY: "auto", padding: 16 }}>
      <h3 style={{ marginBottom: 12, color: "#555", fontSize: 13, textTransform: "uppercase" }}>Patients</h3>
      {patients.map(p => (
        <div
          key={p._id}
          onClick={() => onSelect(p)}
          style={{
            padding: "10px 12px", borderRadius: 8, cursor: "pointer", marginBottom: 6,
            background: selected?._id === p._id ? "#f0f4ff" : "transparent",
            border: selected?._id === p._id ? "1px solid #c7d2fe" : "1px solid transparent"
          }}
        >
          <div style={{ fontWeight: 500, fontSize: 14 }}>{p.firstName} {p.lastName}</div>
          <div style={{ fontSize: 12, color: "#888", marginTop: 2 }}>{p.curveLocation} · {p.treatmentPlan}</div>
        </div>
      ))}
    </div>
  )
}

export default PatientList