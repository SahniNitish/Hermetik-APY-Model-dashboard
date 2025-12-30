import { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Area, AreaChart } from 'recharts'
import { TrendingUp, TrendingDown, Activity, RefreshCw, Layers, Clock, BarChart3, ArrowUpRight, Shield, Zap } from 'lucide-react'
import './App.css'

const API_URL = 'http://localhost:8000'

function App() {
  const [predictions, setPredictions] = useState([])
  const [pools, setPools] = useState([])
  const [selectedPool, setSelectedPool] = useState(null)
  const [poolHistory, setPoolHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [predictionMeta, setPredictionMeta] = useState({})
  const [settings, setSettings] = useState({
    maxLag: 7,
    forecastHorizon: 1,
    topN: 10
  })

  const fetchPredictions = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await axios.post(`${API_URL}/api/predict`, {
        max_lag: settings.maxLag,
        forecast_horizon: settings.forecastHorizon,
        top_n: settings.topN
      })
      setPredictions(response.data.predictions)
      setPredictionMeta({
        date: response.data.prediction_date,
        horizon: response.data.forecast_horizon,
        totalPools: response.data.total_pools
      })
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to fetch predictions')
    }
    setLoading(false)
  }

  const fetchPools = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/pools`)
      setPools(response.data.pools)
    } catch (err) {
      console.error('Failed to fetch pools:', err)
    }
  }

  const fetchPoolHistory = async (poolAddress) => {
    try {
      const response = await axios.get(`${API_URL}/api/pool/${poolAddress}/history`)
      setPoolHistory(response.data.history)
      setSelectedPool({
        address: poolAddress,
        name: response.data.pool_name
      })
    } catch (err) {
      console.error('Failed to fetch pool history:', err)
    }
  }

  useEffect(() => {
    fetchPools()
  }, [])

  const formatGrowthRate = (rate) => {
    const percentage = (Math.exp(rate) - 1) * 100
    return percentage.toFixed(2)
  }

  const formatAddress = (addr) => {
    if (!addr || addr.length < 15) return addr
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  return (
    <div className="app">
      {/* Ambient background */}
      <div className="ambient-bg" />

      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo-section">
            <div className="logo-icon">
              <Layers size={24} />
            </div>
            <div className="logo-text">
              <h1>Hermetik</h1>
              <span className="logo-tagline">DeFi Analytics</span>
            </div>
          </div>
          <div className="header-stats">
            <div className="header-stat">
              <Shield size={14} />
              <span>Secure</span>
            </div>
            <div className="header-stat">
              <Zap size={14} />
              <span>Real-time</span>
            </div>
          </div>
        </div>
      </header>

      <main className="main">
        {/* Hero Section */}
        <section className="hero-section">
          <div className="hero-content">
            <h2>Liquidity Pool Intelligence</h2>
            <p>AI-powered growth predictions for optimal DeFi positioning</p>
          </div>
        </section>

        {/* Controls */}
        <section className="controls-section">
          <div className="controls-grid">
            <div className="control-group">
              <label>
                <Clock size={14} />
                Forecast Horizon
              </label>
              <div className="select-wrapper">
                <select
                  value={settings.forecastHorizon}
                  onChange={(e) => setSettings({...settings, forecastHorizon: parseInt(e.target.value)})}
                >
                  <option value={1}>1 Day</option>
                  <option value={3}>3 Days</option>
                  <option value={7}>7 Days</option>
                </select>
              </div>
            </div>

            <div className="control-group">
              <label>
                <BarChart3 size={14} />
                Analysis Depth
              </label>
              <div className="select-wrapper">
                <select
                  value={settings.maxLag}
                  onChange={(e) => setSettings({...settings, maxLag: parseInt(e.target.value)})}
                >
                  <option value={7}>7 Days</option>
                  <option value={14}>14 Days</option>
                </select>
              </div>
            </div>

            <div className="control-group">
              <label>
                <Layers size={14} />
                Pool Count
              </label>
              <div className="select-wrapper">
                <select
                  value={settings.topN}
                  onChange={(e) => setSettings({...settings, topN: parseInt(e.target.value)})}
                >
                  <option value={5}>Top 5</option>
                  <option value={10}>Top 10</option>
                  <option value={20}>Top 20</option>
                  <option value={50}>Top 50</option>
                </select>
              </div>
            </div>

            <button
              className="analyze-btn"
              onClick={fetchPredictions}
              disabled={loading}
            >
              {loading ? (
                <>
                  <RefreshCw className="spin" size={18} />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Activity size={18} />
                  <span>Run Analysis</span>
                </>
              )}
            </button>
          </div>
        </section>

        {error && (
          <div className="error-banner">
            <span>{error}</span>
          </div>
        )}

        {/* Stats Overview */}
        {predictions.length > 0 && (
          <section className="stats-section">
            <div className="stat-card">
              <div className="stat-icon">
                <Layers size={20} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{predictionMeta.totalPools}</span>
                <span className="stat-label">Pools Analyzed</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">
                <Clock size={20} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{predictionMeta.horizon}D</span>
                <span className="stat-label">Forecast Window</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">
                <TrendingUp size={20} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{predictions.length > 0 ? formatGrowthRate(predictions[0].predicted_growth_rate) : '0'}%</span>
                <span className="stat-label">Top Growth Rate</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">
                <Activity size={20} />
              </div>
              <div className="stat-content">
                <span className="stat-value">{predictionMeta.date}</span>
                <span className="stat-label">Prediction Date</span>
              </div>
            </div>
          </section>
        )}

        {/* Predictions Table */}
        {predictions.length > 0 && (
          <section className="card predictions-card">
            <div className="card-header">
              <div className="card-title">
                <h3>Growth Predictions</h3>
                <span className="badge">Live</span>
              </div>
              <p className="card-subtitle">Ranked by predicted transaction volume growth</p>
            </div>

            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Pool Address</th>
                    <th>Predicted Growth</th>
                    <th>TX Volume</th>
                    <th>Fee Tier</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((pred, index) => (
                    <tr key={pred.pool_address} className={index < 3 ? 'top-rank' : ''}>
                      <td>
                        <span className={`rank-badge rank-${index < 3 ? index + 1 : 'default'}`}>
                          {pred.rank}
                        </span>
                      </td>
                      <td>
                        <div className="address-cell">
                          <code>{formatAddress(pred.pool_address)}</code>
                          <a
                            href={`https://etherscan.io/address/${pred.pool_address}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="etherscan-link"
                          >
                            <ArrowUpRight size={12} />
                          </a>
                        </div>
                      </td>
                      <td>
                        <div className={`growth-cell ${pred.predicted_growth_rate > 0 ? 'positive' : 'negative'}`}>
                          {pred.predicted_growth_rate > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                          <span>{formatGrowthRate(pred.predicted_growth_rate)}%</span>
                        </div>
                      </td>
                      <td>
                        <span className="volume-cell">{pred.current_tx_count?.toLocaleString() || '—'}</span>
                      </td>
                      <td>
                        <span className="fee-badge">{pred.fee_percentage ? `${(pred.fee_percentage * 100).toFixed(2)}%` : '—'}</span>
                      </td>
                      <td>
                        <button
                          className="details-btn"
                          onClick={() => fetchPoolHistory(pred.pool_address)}
                        >
                          Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Charts Grid */}
        {predictions.length > 0 && (
          <div className="charts-grid">
            {/* Bar Chart */}
            <section className="card chart-card">
              <div className="card-header">
                <h3>Growth Comparison</h3>
                <p className="card-subtitle">Top performing pools by predicted growth</p>
              </div>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={predictions.slice(0, 8)} barCategoryGap="20%">
                    <defs>
                      <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#c9bc4a" stopOpacity={1}/>
                        <stop offset="100%" stopColor="#B2A534" stopOpacity={0.8}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(178, 165, 52, 0.1)" vertical={false} />
                    <XAxis
                      dataKey="pool_address"
                      tickFormatter={(addr) => `#${predictions.findIndex(p => p.pool_address === addr) + 1}`}
                      stroke="rgba(255,255,255,0.3)"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tickFormatter={(val) => `${formatGrowthRate(val)}%`}
                      stroke="rgba(255,255,255,0.3)"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      width={60}
                    />
                    <Tooltip
                      formatter={(val) => [`${formatGrowthRate(val)}%`, 'Growth']}
                      labelFormatter={(addr) => `Pool: ${formatAddress(addr)}`}
                      contentStyle={{
                        background: 'rgba(10, 15, 12, 0.95)',
                        border: '1px solid rgba(178, 165, 52, 0.2)',
                        borderRadius: '8px',
                        boxShadow: '0 4px 20px rgba(0,0,0,0.4)'
                      }}
                      itemStyle={{ color: '#B2A534' }}
                      labelStyle={{ color: 'rgba(255,255,255,0.7)', marginBottom: '4px' }}
                    />
                    <Bar
                      dataKey="predicted_growth_rate"
                      fill="url(#barGradient)"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            {/* Pool History */}
            {selectedPool && poolHistory.length > 0 && (
              <section className="card chart-card">
                <div className="card-header">
                  <div>
                    <h3>{selectedPool.name || 'Pool History'}</h3>
                    <code className="pool-code">{formatAddress(selectedPool.address)}</code>
                  </div>
                </div>
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={poolHistory}>
                      <defs>
                        <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#00321d" stopOpacity={0.5}/>
                          <stop offset="100%" stopColor="#00321d" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(178, 165, 52, 0.1)" vertical={false} />
                      <XAxis
                        dataKey="date"
                        stroke="rgba(255,255,255,0.3)"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      />
                      <YAxis
                        stroke="rgba(255,255,255,0.3)"
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        width={50}
                      />
                      <Tooltip
                        contentStyle={{
                          background: 'rgba(10, 15, 12, 0.95)',
                          border: '1px solid rgba(178, 165, 52, 0.2)',
                          borderRadius: '8px',
                          boxShadow: '0 4px 20px rgba(0,0,0,0.4)'
                        }}
                        labelFormatter={(date) => new Date(date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
                        itemStyle={{ color: '#B2A534' }}
                        labelStyle={{ color: 'rgba(255,255,255,0.7)', marginBottom: '4px' }}
                      />
                      <Area
                        type="monotone"
                        dataKey="tx_count"
                        stroke="#B2A534"
                        strokeWidth={2}
                        fill="url(#areaGradient)"
                        name="Transactions"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </section>
            )}
          </div>
        )}

        {/* Empty State */}
        {predictions.length === 0 && !loading && !error && (
          <section className="empty-state">
            <div className="empty-icon">
              <Activity size={48} />
            </div>
            <h3>Ready to Analyze</h3>
            <p>Configure your parameters above and run the analysis to discover high-growth liquidity pools.</p>
            <button className="analyze-btn" onClick={fetchPredictions}>
              <Activity size={18} />
              <span>Run Analysis</span>
            </button>
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        <p>Powered by LightGBM Machine Learning</p>
      </footer>
    </div>
  )
}

export default App
