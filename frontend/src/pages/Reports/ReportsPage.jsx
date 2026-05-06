import { useState } from 'react'
import Layout from '../../components/Layout'
import { downloadPacfa, downloadOccupancy, downloadRevenue, downloadUpcoming, downloadOpenIncidents } from '../../api/reports'
import { format, subDays } from 'date-fns'

function ReportCard({ title, description, children }) {
  return (
    <div className="card" style={{ padding: 20, marginBottom: 16 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>{title}</h3>
      <p style={{ fontSize: 13, color: 'var(--text-sub)', marginBottom: 14 }}>{description}</p>
      {children}
    </div>
  )
}

export default function ReportsPage() {
  const today  = format(new Date(), 'yyyy-MM-dd')
  const month0 = format(subDays(new Date(), 30), 'yyyy-MM-dd')

  const [occStart, setOccStart] = useState(month0)
  const [occEnd,   setOccEnd]   = useState(today)
  const [revStart, setRevStart] = useState(month0)
  const [revEnd,   setRevEnd]   = useState(today)
  const [loading,  setLoading]  = useState({})
  const [error,    setError]    = useState({})

  async function run(key, fn) {
    setLoading(l => ({ ...l, [key]: true }))
    setError(e => ({ ...e, [key]: null }))
    try { await fn() }
    catch (e) { setError(err => ({ ...err, [key]: e.response?.data?.detail || 'Failed to generate report' })) }
    finally { setLoading(l => ({ ...l, [key]: false })) }
  }

  function Btn({ k, label, onClick }) {
    return (
      <div>
        <button className="btn btn-primary btn-sm" disabled={loading[k]} onClick={() => run(k, onClick)}>
          {loading[k] ? 'Generating…' : `⬇ ${label}`}
        </button>
        {error[k] && <p className="error-text" style={{ marginTop: 6 }}>{error[k]}</p>}
      </div>
    )
  }

  return (
    <Layout>
      <div className="page-content">
        <div className="page-header"><h1>Reports</h1></div>

        <ReportCard
          title="PACFA Compliance"
          description="Point-in-time compliance report for all active stays. Includes sqft requirements, duration multipliers, and 181+ day activity gaps."
        >
          <Btn k="pacfa" label="Download PDF" onClick={downloadPacfa} />
        </ReportCard>

        <ReportCard
          title="Occupancy Rate"
          description="Kennel utilization percentage by day, size class breakdown, and peak occupancy dates for a date range."
        >
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="form-field" style={{ marginBottom: 0 }}>
              <label>Start Date</label>
              <input type="date" value={occStart} onChange={e => setOccStart(e.target.value)} />
            </div>
            <div className="form-field" style={{ marginBottom: 0 }}>
              <label>End Date</label>
              <input type="date" value={occEnd} onChange={e => setOccEnd(e.target.value)} />
            </div>
            <Btn k="occ" label="Download PDF" onClick={() => downloadOccupancy(new Date(occStart), new Date(occEnd))} />
          </div>
        </ReportCard>

        <ReportCard
          title="Revenue Summary"
          description="Total revenue, revenue by size class, activity revenue, discounts, and unpaid balances for a date range."
        >
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="form-field" style={{ marginBottom: 0 }}>
              <label>Start Date</label>
              <input type="date" value={revStart} onChange={e => setRevStart(e.target.value)} />
            </div>
            <div className="form-field" style={{ marginBottom: 0 }}>
              <label>End Date</label>
              <input type="date" value={revEnd} onChange={e => setRevEnd(e.target.value)} />
            </div>
            <Btn k="rev" label="Download PDF" onClick={() => downloadRevenue(new Date(revStart), new Date(revEnd))} />
          </div>
        </ReportCard>

        <ReportCard
          title="Upcoming Check-ins and Check-outs"
          description="Today and next 7 days: dog, owner, kennel, scheduled time, phase, and status."
        >
          <Btn k="upcoming" label="Download PDF" onClick={downloadUpcoming} />
        </ReportCard>

        <ReportCard
          title="Open Incidents and Issues"
          description="All unresolved incident reports and kennel issues."
        >
          <Btn k="incidents" label="Download PDF" onClick={downloadOpenIncidents} />
        </ReportCard>
      </div>
    </Layout>
  )
}
