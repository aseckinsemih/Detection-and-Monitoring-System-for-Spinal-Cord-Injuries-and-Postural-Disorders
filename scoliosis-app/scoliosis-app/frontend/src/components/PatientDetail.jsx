import { useState, useEffect } from "react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts"
import { PatientService } from "../services/api"

function PatientDetail({ patient }) {
  const [telemetry, setTelemetry] = useState(null)
  const [isLive, setIsLive] = useState(false)
  const [polling, setPolling] = useState(true)

  useEffect(() => {
    if (!patient) return
    
    const fetchTelemetry = async () => {
      try {
        const data = await PatientService.getLatestTelemetry("ST-2026-001")
        setTelemetry(data)
        setIsLive(true)
      } catch (err) {
        setIsLive(false)
        const t = Date.now() / 1000
        setTelemetry({
          patient_id: "ST-2026-001",
          omuz_asimetrisi: Math.abs(2.4 + Math.sin(t) * 0.4),
          omurga_roll_acileri: [
            1.2 + Math.sin(t * 0.5) * 0.2,
            -2.5 + Math.cos(t * 0.5) * 0.3,
            3.1 + Math.sin(t * 0.8) * 0.5,
            -1.4 + Math.cos(t * 0.6) * 0.2,
            0.8 + Math.sin(t * 0.4) * 0.1
          ],
          serit_basinc_fsr: [
            Math.max(0, 0.45 + Math.sin(t) * 0.1),
            Math.max(0, 0.62 + Math.cos(t * 1.2) * 0.15),
            Math.max(0, 0.20 + Math.sin(t * 0.8) * 0.05),
            Math.max(0, 0.78 + Math.cos(t * 0.5) * 0.12),
            Math.max(0, 0.12 + Math.sin(t * 1.5) * 0.08)
          ],
          nokta_basinc_fsr: [
            Math.max(0, 0.30 + Math.sin(t * 0.9) * 0.05), Math.max(0, 0.42 + Math.cos(t * 0.7) * 0.1), Math.max(0, 0.15 + Math.sin(t) * 0.03),
            Math.max(0, 0.55 + Math.cos(t * 1.1) * 0.12), Math.max(0, 0.82 + Math.sin(t * 0.4) * 0.08), Math.max(0, 0.68 + Math.cos(t * 0.8) * 0.15),
            Math.max(0, 0.25 + Math.sin(t * 1.3) * 0.05), Math.max(0, 0.18 + Math.cos(t) * 0.04), Math.max(0, 0.05 + Math.sin(t * 0.5) * 0.02)
          ]
        })
      }
    }

    fetchTelemetry()
    let intervalId
    if (polling) {
      intervalId = setInterval(fetchTelemetry, 3000)
    }
    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }, [patient, polling])

  if (!patient) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#aaa" }}>
      Select a patient to view their records
    </div>
  )

  const lastVisit = patient.visits?.[patient.visits.length - 1]

  const chartData = (patient.visits || []).map(v => ({
    date: v.visitDate,
    angle: v.cobbAngle
  }))

  const cobbColor = (angle) => {
    if (angle < 25) return "#16a34a"
    if (angle < 40) return "#d97706"
    return "#dc2626"
  }

  const currentAngle = lastVisit?.cobbAngle ?? patient.initialCobbAngle ?? 0

  return (
    <div style={{ flex: 1, padding: 24, overflowY: "auto" }}>

      {/* Header */}
<div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 24 }}>
  <div style={{
    width: 80, height: 80, borderRadius: "50%", overflow: "hidden",
    background: "#f0f0f0", flexShrink: 0, border: "2px solid #e0e0e0",
    display: "flex", alignItems: "center", justifyContent: "center"
  }}>
    {patient.photo
      ? <img src={patient.photo} alt="Patient" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      : <span style={{ fontSize: 28 }}>👤</span>
    }
  </div>
  <div>
    <h2 style={{ marginBottom: 4 }}>{patient.firstName} {patient.lastName}</h2>
    <p style={{ color: "#888", fontSize: 14 }}>
      {patient.gender} · Born {patient.dateOfBirth} · {patient.diagnosisType} scoliosis
    </p>
  </div>
</div>

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
        {[
          {
            label: "Current Cobb Angle",
            value: currentAngle + "°",
            sub: lastVisit?.spineRegion ?? "—",
            color: cobbColor(currentAngle)
          },
          {
            label: "Progression",
            value: lastVisit?.progression != null
              ? (lastVisit.progression > 0 ? "+" : "") + lastVisit.progression + "°"
              : "—",
            sub: "since last visit",
            color: lastVisit?.progression > 0 ? "#dc2626" : "#16a34a"
          },
          {
            label: "Risser Sign",
            value: (patient.rissersSign ?? "—") + " / 5",
            sub: "skeletal maturity",
            color: "#4f46e5"
          },
          {
            label: "Treatment",
            value: patient.treatmentPlan ?? "—",
            sub: patient.braceType
              ? patient.braceType + (patient.braceHoursPerDay ? " · " + patient.braceHoursPerDay + "h/day" : "")
              : "—",
            color: "#0891b2"
          },
        ].map(s => (
          <div key={s.label} style={{ background: "#f9f9f9", borderRadius: 8, padding: 14 }}>
            <div style={{ fontSize: 12, color: "#888", marginBottom: 6 }}>{s.label}</div>
            <div style={{ fontSize: 22, fontWeight: 600, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 12, color: "#aaa", marginTop: 4 }}>{s.sub}</div>
          </div>
        ))}
      </div>

      {/* Cobb angle chart */}
      {chartData.length > 0 ? (
        <div style={{ background: "#f9f9f9", borderRadius: 8, padding: 16, marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, color: "#555", marginBottom: 16 }}>Cobb angle over time</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#aaa" }} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "#aaa" }} unit="°" />
              <Tooltip formatter={(val) => val + "°"} labelStyle={{ fontSize: 12 }} />
              <ReferenceLine y={25} stroke="#16a34a" strokeDasharray="4 4" label={{ value: "25° observe", fontSize: 10, fill: "#16a34a" }} />
              <ReferenceLine y={40} stroke="#dc2626" strokeDasharray="4 4" label={{ value: "40° surgery", fontSize: 10, fill: "#dc2626" }} />
              <Line
                type="monotone"
                dataKey="angle"
                stroke="#4f46e5"
                strokeWidth={2}
                dot={{ r: 5, fill: "#4f46e5" }}
                activeDot={{ r: 7 }}
              />
            </LineChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", gap: 16, marginTop: 10, fontSize: 11, color: "#aaa" }}>
            <span style={{ color: "#16a34a" }}>— Below 25°: observation</span>
            <span style={{ color: "#d97706" }}>— 25°–40°: bracing</span>
            <span style={{ color: "#dc2626" }}>— Above 40°: surgery risk</span>
          </div>
        </div>
      ) : (
        <div style={{ background: "#f9f9f9", borderRadius: 8, padding: 16, marginBottom: 24, color: "#aaa", fontSize: 14 }}>
          No visits yet — add a visit to see the Cobb angle chart.
        </div>
      )}

      {/* Visit history */}
      <h3 style={{ fontSize: 14, color: "#555", marginBottom: 12 }}>Visit history</h3>
      {patient.visits?.length === 0 && (
        <p style={{ color: "#aaa", fontSize: 14 }}>No visits recorded yet.</p>
      )}
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ background: "#f5f5f5" }}>
            {["Date", "Cobb Angle", "Region", "Change", "Pain", "Physician", "Notes"].map(h => (
              <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontWeight: 500, fontSize: 12, color: "#666" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...(patient.visits || [])].reverse().map((v, i) => (
            <tr key={i} style={{ borderBottom: "1px solid #f0f0f0" }}>
              <td style={{ padding: "10px 12px" }}>{v.visitDate}</td>
              <td style={{ padding: "10px 12px", fontWeight: 500, color: cobbColor(v.cobbAngle) }}>{v.cobbAngle}°</td>
              <td style={{ padding: "10px 12px" }}>{v.spineRegion}</td>
              <td style={{ padding: "10px 12px", color: v.progression > 0 ? "#dc2626" : "#16a34a", fontWeight: 500 }}>
                {v.progression != null ? (v.progression > 0 ? "+" : "") + v.progression + "°" : "—"}
              </td>
              <td style={{ padding: "10px 12px" }}>{v.painLevel ?? "—"}</td>
              <td style={{ padding: "10px 12px" }}>{v.physician}</td>
              <td style={{ padding: "10px 12px", color: "#888" }}>{v.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Smart Corset Telemetry Dashboard */}
      {telemetry && (
        <div style={{ background: "#111827", borderRadius: 12, padding: 20, marginBottom: 24, color: "#f3f4f6", border: "1px solid #1f2937", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)" }}>
          <style>{`
            @keyframes pulse {
              0% { transform: scale(0.95); opacity: 0.5; }
              50% { transform: scale(1.05); opacity: 1; }
              100% { transform: scale(0.95); opacity: 0.5; }
            }
          `}</style>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#f9fafb", display: "flex", alignItems: "center", gap: 8 }}>
                🔌 Smart Corset Cloud Telemetry
              </h3>
              <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>
                Real-time postural tracking and FSR matrix data
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <div style={{
                display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 600,
                padding: "4px 10px", borderRadius: 12,
                background: isLive ? "rgba(16, 185, 129, 0.15)" : "rgba(59, 130, 246, 0.15)",
                color: isLive ? "#10b981" : "#3b82f6",
                border: `1px solid ${isLive ? "rgba(16, 185, 129, 0.3)" : "rgba(59, 130, 246, 0.3)"}`
              }}>
                <span style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: isLive ? "#10b981" : "#3b82f6",
                  animation: "pulse 1.5s infinite"
                }} />
                {isLive ? "LIVE SYNCED FROM CLOUD" : "HARDWARE DEMO MODE"}
              </div>
              <button 
                onClick={() => setPolling(!polling)}
                style={{
                  background: "transparent", border: "1px solid #374151", color: "#d1d5db",
                  borderRadius: 6, padding: "4px 8px", fontSize: 11, cursor: "pointer"
                }}
              >
                {polling ? "Pause Polling" : "Resume Polling"}
              </button>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr 1.2fr", gap: 16 }}>
            {/* Posture Analysis */}
            <div style={{ background: "#1f2937", borderRadius: 8, padding: 14, display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{ fontSize: 12, color: "#9ca3af", fontWeight: 500, alignSelf: "flex-start", marginBottom: 12 }}>
                Postural Alignment
              </div>
              
              <div style={{ display: "flex", gap: 20, alignItems: "center", width: "100%", justifyContent: "center" }}>
                {/* SVG Spine Path */}
                <div style={{ width: 100, height: 160, background: "#111827", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
                  <svg width="100" height="150" viewBox="0 0 100 150">
                    <line x1="50" y1="10" x2="50" y2="140" stroke="#374151" strokeDasharray="3 3" strokeWidth="1.5" />
                    {/* Spine representation */}
                    {(() => {
                      let points = [{ x: 50, y: 10 }];
                      let currentX = 50;
                      let currentY = 10;
                      telemetry.omurga_roll_acileri.forEach((angle) => {
                        let rad = (angle * Math.PI) / 180;
                        currentX += 16 * Math.sin(rad);
                        currentY += 24;
                        points.push({ x: currentX, y: currentY });
                      });
                      
                      let pathD = `M ${points[0].x} ${points[0].y} `;
                      for (let i = 1; i < points.length; i++) {
                        let xc = (points[i - 1].x + points[i].x) / 2;
                        let yc = (points[i - 1].y + points[i].y) / 2;
                        pathD += `Q ${points[i - 1].x} ${points[i - 1].y}, ${xc} ${yc} T ${points[i].x} ${points[i].y} `;
                      }
                      
                      return (
                        <>
                          <path d={pathD} fill="none" stroke="#4f46e5" strokeWidth="3" strokeLinecap="round" />
                          {points.map((p, idx) => (
                            <circle key={idx} cx={p.x} cy={p.y} r={idx === 0 || idx === points.length - 1 ? 4 : 3} fill={idx === 0 || idx === points.length - 1 ? "#ef4444" : "#f59e0b"} />
                          ))}
                        </>
                      );
                    })()}
                  </svg>
                </div>

                <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ background: "#111827", padding: "8px 10px", borderRadius: 6 }}>
                    <div style={{ fontSize: 10, color: "#9ca3af" }}>Shoulder Asymmetry</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: telemetry.omuz_asimetrisi > 5.0 ? "#ef4444" : telemetry.omuz_asimetrisi > 3.0 ? "#f59e0b" : "#10b981", marginTop: 2 }}>
                      {telemetry.omuz_asimetrisi.toFixed(2)}°
                    </div>
                  </div>
                  <div style={{ background: "#111827", padding: "8px 10px", borderRadius: 6 }}>
                    <div style={{ fontSize: 10, color: "#9ca3af" }}>Cobb Angle Est.</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "#10b981", marginTop: 2 }}>
                      {Math.max(...telemetry.omurga_roll_acileri.map(Math.abs)).toFixed(1)}°
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* FSR Left Strip */}
            <div style={{ background: "#1f2937", borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 12, color: "#9ca3af", fontWeight: 500, marginBottom: 12 }}>
                FSR Strip Sensors (Left)
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {telemetry.serit_basinc_fsr.map((val, idx) => {
                  const getFSRColor = (v) => {
                    const r = Math.round(239 * v + 55 * (1 - v));
                    const g = Math.round(68 * v + 65 * (1 - v));
                    const b = Math.round(68 * v + 81 * (1 - v));
                    return `rgba(${r}, ${g}, ${b}, ${0.15 + v * 0.85})`;
                  };
                  return (
                    <div key={idx} style={{ display: "flex", alignItems: "center", gap: 10, background: "#111827", padding: "6px 10px", borderRadius: 6 }}>
                      <div style={{ fontSize: 10, color: "#9ca3af", width: 45 }}>STRIP {idx+1}</div>
                      <div style={{ flex: 1, height: 8, background: "#1f2937", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${val * 100}%`, background: `linear-gradient(90deg, #4f46e5, #ef4444)`, borderRadius: 4 }} />
                      </div>
                      <div style={{
                        width: 14, height: 14, borderRadius: "50%",
                        background: getFSRColor(val), border: "1px solid rgba(255,255,255,0.1)"
                      }} />
                      <div style={{ fontSize: 11, color: "#f3f4f6", fontWeight: 600, width: 28, textAlign: "right" }}>
                        {val.toFixed(2)}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* FSR Right Matrix */}
            <div style={{ background: "#1f2937", borderRadius: 8, padding: 14, display: "flex", flexDirection: "column" }}>
              <div style={{ fontSize: 12, color: "#9ca3af", fontWeight: 500, marginBottom: 12 }}>
                FSR Point Matrix (Right)
              </div>
              
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6, margin: "auto 0" }}>
                {telemetry.nokta_basinc_fsr.map((val, idx) => {
                  const getFSRColor = (v) => {
                    const r = Math.round(239 * v + 55 * (1 - v));
                    const g = Math.round(68 * v + 65 * (1 - v));
                    const b = Math.round(68 * v + 81 * (1 - v));
                    return `rgba(${r}, ${g}, ${b}, ${0.15 + v * 0.85})`;
                  };
                  return (
                    <div key={idx} style={{
                      aspectRatio: "1.2", background: "#111827", borderRadius: 6,
                      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                      border: `1px solid ${val > 0.6 ? "rgba(239, 68, 68, 0.4)" : "transparent"}`
                    }}>
                      <div style={{ fontSize: 8, color: "#9ca3af", marginBottom: 2 }}>P{idx+1}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: val > 0.7 ? "#ef4444" : val > 0.4 ? "#f59e0b" : "#f3f4f6" }}>
                        {val.toFixed(2)}
                      </div>
                      <div style={{
                        width: 8, height: 8, borderRadius: "50%", marginTop: 4,
                        background: getFSRColor(val)
                      }} />
                    </div>
                  );
                })}
              </div>
            </div>

          </div>
        </div>
      )}

      {/* Treatment details */}
      <h3 style={{ fontSize: 14, color: "#555", margin: "24px 0 12px" }}>Treatment details</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {[
          { label: "Diagnosis Type", value: patient.diagnosisType },
          { label: "Curve Location", value: patient.curveLocation },
          { label: "Current Plan", value: patient.treatmentPlan },
          { label: "Brace Type", value: patient.braceType || "—" },
          { label: "Brace Hours/Day", value: patient.braceHoursPerDay ? patient.braceHoursPerDay + "h" : "—" },
          { label: "Physical Therapy", value: patient.physicalTherapy ? "Yes" : "No" },
        ].map(item => (
          <div key={item.label} style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
            <div style={{ fontSize: 11, color: "#aaa", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>{item.label}</div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>{item.value}</div>
          </div>
        ))}
      </div>

    </div>
  )
}

export default PatientDetail