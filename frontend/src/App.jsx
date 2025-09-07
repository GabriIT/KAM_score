import React, { useEffect, useMemo, useState } from 'react'
import axios from 'axios'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer } from 'recharts'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function download(url, filename) {
  const res = await fetch(url, { method: 'GET', credentials: 'omit' });
  if (!res.ok) { alert(`Download failed: ${res.status} ${res.statusText}`); return; }
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = href; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(href);
}

export default function App() {
  const [state, setState] = useState(null)
  const [scores, setScores] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selectedKam, setSelectedKam] = useState('')
  const [loggedInKam, setLoggedInKam] = useState('')

  const [inputMonth, setInputMonth] = useState('2026-01-01')
  const [addedPP, setAddedPP] = useState('80')
  const [addedLVP, setAddedLVP] = useState('40')
  const [newProjects, setNewProjects] = useState('2')

  const [dataset, setDataset] = useState(null)
  const [inputsData, setInputsData] = useState(null)
  const [datasetFilterKam, setDatasetFilterKam] = useState('All')
  const [datasetFilterMonth, setDatasetFilterMonth] = useState('All')
  const [inputsFilterKam, setInputsFilterKam] = useState('All')
  const [inputsFilterMonth, setInputsFilterMonth] = useState('All')

  const months = useMemo(() => (scores ? Array.from(new Set(scores.monthly.map(m => m.month))).sort() : []), [scores])
  const kams = useMemo(() => (scores ? Array.from(new Set(scores.monthly.map(m => m.kam))) : (state?.kams?.map(k=>k.name) || [])), [scores, state])

  const datasetKams = useMemo(() => dataset ? Array.from(new Set(dataset.rows.map(r=>r.kam))).sort() : [], [dataset])
  const datasetMonths = useMemo(() => dataset ? Array.from(new Set(dataset.rows.map(r=>r.month.slice(0,7)))).sort() : [], [dataset])
  const inputsKams = useMemo(() => inputsData ? Array.from(new Set(inputsData.rows.map(r=>r.kam))).sort() : [], [inputsData])
  const inputsMonths = useMemo(() => inputsData ? Array.from(new Set(inputsData.rows.map(r=>r.month.slice(0,7)))).sort() : [], [inputsData])

  const filteredDatasetRows = useMemo(() => {
    if (!dataset) return []
    return dataset.rows.filter(r =>
      (datasetFilterKam === 'All' || r.kam === datasetFilterKam) &&
      (datasetFilterMonth === 'All' || r.month.slice(0,7) === datasetFilterMonth)
    )
  }, [dataset, datasetFilterKam, datasetFilterMonth])

  const filteredInputsRows = useMemo(() => {
    if (!inputsData) return []
    return inputsData.rows.filter(r =>
      (inputsFilterKam === 'All' || r.kam === inputsFilterKam) &&
      (inputsFilterMonth === 'All' || r.month.slice(0,7) === inputsFilterMonth)
    )
  }, [inputsData, inputsFilterKam, inputsFilterMonth])

  async function loadState() { const r = await axios.get(`${API_BASE}/state`); setState(r.data); if (!selectedKam && r.data.kams?.length) setSelectedKam(r.data.kams[0].name) }
  async function loadScores() { const r = await axios.get(`${API_BASE}/scores`); setScores(r.data); if (!selectedKam && r.data?.monthly?.length) setSelectedKam(r.data.monthly[0].kam) }
  async function loadDataset() { const r = await fetch(`${API_BASE}/dataset`); setDataset(await r.json()) }
  async function loadInputs() { const r = await fetch(`${API_BASE}/inputs`); setInputsData(await r.json()) }

  async function seed() {
    setLoading(true)
    try {
      await axios.post(`${API_BASE}/seed`, { start_month:'2025-09-01', months:4, kam_names:['Alice','Bob','Carla','Dario'], regions:['China Consumer','China Industry','JP','TW'], random_seed:Math.floor(Math.random()*100000) })
      await loadState(); await loadScores()
    } finally { setLoading(false) }
  }

  useEffect(() => { loadState().catch(()=>{}); loadScores().catch(()=>{}) }, [])

  const filteredMonthly = useMemo(() => {
    if (!scores) return []
    return scores.monthly.filter(r => !selectedKam || r.kam === selectedKam).map(r => ({...r, monthLabel: r.month?.slice(0,7)}))
  }, [scores, selectedKam])

  async function submitInputMonth(e) {
    e.preventDefault()
    if (!loggedInKam) { alert('Please log in as a KAM first.'); return }
    setLoading(true)
    try {
      const payload = { kam_name: loggedInKam, month: inputMonth, new_projects: parseInt(newProjects||'2',10), added_pp: parseFloat(addedPP||'0'), added_lvp: parseFloat(addedLVP||'0'), avg_sop_month: 6, foc_ratio_pp: 0.5, foc_ratio_lvp: 0.7 }
      await axios.post(`${API_BASE}/input_month`, payload, { headers:{'Content-Type':'application/json'} })
      await loadScores(); await loadInputs(); await loadDataset();
      alert('Month achievements saved.')
    } catch (err) { alert('Failed to save: ' + (err?.response?.data?.detail || err.message)) }
    finally { setLoading(false) }
  }

  return (
    <div style={{fontFamily:'system-ui, sans-serif', padding: 20, maxWidth: 1200, margin: '0 auto'}}>
      <div style={{display:'flex',alignItems:'center',gap:12}}>
        <img src="/ems_logo.png" alt="EMS" style={{height:36}} />
        <h1 style={{margin:0}}>KAM Scores Dashboard</h1>
      </div>
      <p>Backend: <code>{API_BASE}</code></p>

      <div style={{display:'flex', gap:10, flexWrap:'wrap', alignItems:'center', marginBottom:16}}>
        <button onClick={seed} disabled={loading} style={{padding:'8px 12px'}}>Seed 4-month Mock</button>
        <button onClick={loadScores} disabled={loading} style={{padding:'8px 12px'}}>Refresh Scores</button>
        <button onClick={() => download(`${API_BASE}/scores_csv`, 'monthly_scores.csv')} style={{padding:'8px 12px'}}>Download Monthly CSV</button>
        <button onClick={() => download(`${API_BASE}/scores_cumulative_csv`, 'cumulative_scores.csv')} style={{padding:'8px 12px'}}>Download Cumulative CSV</button>
        <button onClick={() => download(`${API_BASE}/dataset_csv`, 'dataset_all_rows.csv')} style={{padding:'8px 12px'}}>Download Dataset CSV</button>
        <button onClick={() => download(`${API_BASE}/inputs_csv`, 'inputs_manual_rows.csv')} style={{padding:'8px 12px'}}>Download Inputs CSV</button>
        <button onClick={loadDataset} style={{padding:'8px 12px'}}>Show Dataset</button>
        <button onClick={loadInputs} style={{padding:'8px 12px'}}>Show KAM Inputs</button>

        {dataset && (
          <span style={{marginLeft:8}}>
            <label>Dataset KAM:&nbsp;
              <select value={datasetFilterKam} onChange={e=>setDatasetFilterKam(e.target.value)}>
                <option>All</option>
                {datasetKams.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </label>
            &nbsp;Month:&nbsp;
            <select value={datasetFilterMonth} onChange={e=>setDatasetFilterMonth(e.target.value)}>
              <option>All</option>
              {datasetMonths.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </span>
        )}

        {inputsData && (
          <span style={{marginLeft:8}}>
            <label>Inputs KAM:&nbsp;
              <select value={inputsFilterKam} onChange={e=>setInputsFilterKam(e.target.value)}>
                <option>All</option>
                {inputsKams.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </label>
            &nbsp;Month:&nbsp;
            <select value={inputsFilterMonth} onChange={e=>setInputsFilterMonth(e.target.value)}>
              <option>All</option>
              {inputsMonths.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </span>
        )}
      </div>

      <div style={{border:'1px solid #ddd', borderRadius:8, padding:12, marginBottom:16, background:'#fafafa'}}>
        <h3>Login as KAM (demo only)</h3>
        <div style={{display:'flex', gap:8, alignItems:'center'}}>
          <select value={loggedInKam} onChange={(e)=>setLoggedInKam(e.target.value)}>
            <option value="">Choose KAM…</option>
            {kams.map(k => <option key={k} value={k}>{k}</option>)}
          </select>
          <span>{loggedInKam ? `Logged in as ${loggedInKam}` : 'Not logged in'}</span>
        </div>
      </div>

      <div style={{border:'1px solid #ddd', borderRadius:8, padding:12, marginBottom:24}}>
        <h3>Input Achievements (Jan–Apr 2026)</h3>
        <form onSubmit={submitInputMonth} style={{display:'grid', gridTemplateColumns:'repeat(4, minmax(180px, 1fr))', gap:12}}>
          <label>Month
            <select value={inputMonth} onChange={(e)=>setInputMonth(e.target.value)}>
              <option value="2026-01-01">Jan 2026</option>
              <option value="2026-02-01">Feb 2026</option>
              <option value="2026-03-01">Mar 2026</option>
              <option value="2026-04-01">Apr 2026</option>
            </select>
          </label>
          <label>Added PP (tons)
            <input type="number" step="0.01" value={addedPP} onChange={(e)=>setAddedPP(e.target.value)} />
          </label>
          <label>Added LVP (tons)
            <input type="number" step="0.01" value={addedLVP} onChange={(e)=>setAddedLVP(e.target.value)} />
          </label>
          <label>New Projects
            <input type="number" min="1" max="8" value={newProjects} onChange={(e)=>setNewProjects(e.target.value)} />
          </label>
          <div style={{gridColumn:'1 / -1'}}>
            <button type="submit" disabled={loading} style={{padding:'8px 12px'}}>Save Month</button>
          </div>
        </form>
        <p style={{fontSize:13, color:'#555', marginTop:8}}>Promotions are tracked per project; SOP delays penalize using last month's FOC-2026 for delayed projects; inactivity (no new projects) is −100.</p>
      </div>

      {!scores && <p>No scores yet. Click "Seed 4-month Mock".</p>}
      {scores && (
        <>
          <h2>Monthly Scores (table)</h2>
          <table border="1" cellPadding="6" style={{borderCollapse:'collapse', width:'100%'}}>
            <thead><tr><th>KAM</th><th>Month</th><th>PP +pts</th><th>LVP +pts</th><th>SOP delay -pts</th><th>Vol ↓ -pts</th><th>PP ↓ -pts</th><th>Total</th></tr></thead>
            <tbody>
              {scores.monthly.map((row, idx) => (
                <tr key={idx}>
                  <td>{row.kam}</td><td>{row.month}</td>
                  <td>{row.points_gained_pp.toFixed(1)}</td>
                  <td>{row.points_gained_lvp.toFixed(1)}</td>
                  <td>{row.points_lost_sop_delay.toFixed(1)}</td>
                  <td>{row.points_lost_volume_dec.toFixed(1)}</td>
                  <td>{row.points_lost_pp_dec.toFixed(1)}</td>
                  <td><b>{row.total.toFixed(1)}</b></td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2 style={{marginTop:24}}>Cumulative</h2>
          <table border="1" cellPadding="6" style={{borderCollapse:'collapse', width:'100%'}}>
            <thead><tr><th>KAM</th><th>Cumulative Points</th></tr></thead>
            <tbody>{Object.entries(scores.cumulative_by_kam).map(([k,v]) => (<tr key={k}><td>{k}</td><td><b>{v.toFixed(1)}</b></td></tr>))}</tbody>
          </table>

          <h2 style={{marginTop:32}}>Per-KAM Monthly Breakdown – Totals</h2>
          <div style={{height:360, background:'#fafafa', padding:12, border:'1px solid #eee', borderRadius:8}}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={scores.monthly.filter(r => !selectedKam || r.kam === selectedKam).map(r => ({...r, monthLabel: r.month?.slice(0,7)}))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="monthLabel" /><YAxis /><Tooltip /><Legend />
                <Line type="monotone" dataKey="total" name={`${selectedKam || 'KAM'} total`} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <h2 style={{marginTop:24}}>Per-KAM Monthly Components</h2>
          <div style={{height:380, background:'#fafafa', padding:12, border:'1px solid #eee', borderRadius:8}}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scores.monthly.filter(r => !selectedKam || r.kam === selectedKam).map(r => ({...r, monthLabel: r.month?.slice(0,7)}))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="monthLabel" /><YAxis /><Tooltip /><Legend />
                <Bar dataKey="points_gained_pp" stackId="a" name="PP +pts" />
                <Bar dataKey="points_gained_lvp" stackId="a" name="LVP +pts" />
                <Bar dataKey="points_lost_sop_delay" stackId="b" name="SOP delay -pts" />
                <Bar dataKey="points_lost_volume_dec" stackId="b" name="Vol ↓ -pts" />
                <Bar dataKey="points_lost_pp_dec" stackId="b" name="PP ↓ -pts" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {dataset && (
        <div style={{marginTop:24}}>
          <h2>Randomly Generated Dataset (All Rows)</h2>
          <div style={{maxHeight:360, overflow:'auto', border:'1px solid #eee'}}>
            <table border="1" cellPadding="6" style={{borderCollapse:'collapse', width:'100%'}}>
              <thead><tr><th>KAM</th><th>Project</th><th>Month</th><th>PP</th><th>LVP</th><th>SOP</th><th>FOC-2026 PP</th><th>FOC-2026 Sec</th><th>Source</th></tr></thead>
              <tbody>
                {filteredDatasetRows.map((r,i)=>(
                  <tr key={i}><td>{r.kam}</td><td>{r.project_code}</td><td>{r.month}</td><td>{r.pp}</td><td>{r.lvp}</td><td>{r.sop_ym}</td><td>{r.foc2026_pp}</td><td>{r.foc2026_sec}</td><td>{r.source}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{fontSize:12, color:'#555'}}>Shown: {filteredDatasetRows.length} / Total: {dataset.count}</p>
        </div>
      )}

      {inputsData && (
        <div style={{marginTop:24}}>
          <h2>KAM Manual Inputs (Jan–Apr 2026)</h2>
          <div style={{maxHeight:360, overflow:'auto', border:'1px solid #eee'}}>
            <table border="1" cellPadding="6" style={{borderCollapse:'collapse', width:'100%'}}>
              <thead><tr><th>KAM</th><th>Project</th><th>Month</th><th>PP</th><th>LVP</th><th>SOP</th><th>FOC-2026 PP</th><th>FOC-2026 Sec</th></tr></thead>
              <tbody>
                {filteredInputsRows.map((r,i)=>(
                  <tr key={i}><td>{r.kam}</td><td>{r.project_code}</td><td>{r.month}</td><td>{r.pp}</td><td>{r.lvp}</td><td>{r.sop_ym}</td><td>{r.foc2026_pp}</td><td>{r.foc2026_sec}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{fontSize:12, color:'#555'}}>Shown: {filteredInputsRows.length} / Total: {inputsData.count}</p>
        </div>
      )}
    </div>
  )
}
